//
// Copyright (C) 2020 OpenSim Ltd.
//
// SPDX-License-Identifier: LGPL-3.0-or-later
//


#include "inet/queueing/base/PacketFlowBase.h"

#include "inet/common/ModuleAccess.h"

namespace inet {
namespace queueing {

void PacketFlowBase::initialize(int stage)
{
    PacketProcessorBase::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        inputGate = gate("in");
        outputGate = gate("out");
        producer.reference(inputGate, false);
        consumer.reference(outputGate, false);
        provider.reference(inputGate, false);
        collector.reference(outputGate, false);
        collection.reference(inputGate, false);
    }
    else if (stage == INITSTAGE_QUEUEING) {
        checkPacketOperationSupport(inputGate);
        checkPacketOperationSupport(outputGate);
    }
}

void PacketFlowBase::handleMessage(cMessage *message)
{
    auto packet = check_and_cast<Packet *>(message);
    pushPacket(packet, packet->getArrivalGate());
}

void PacketFlowBase::checkPacketStreaming(Packet *packet)
{
    if (inProgressStreamId != -1 && (packet == nullptr || packet->getTreeId() != inProgressStreamId))
        throw cRuntimeError("Another packet streaming operation is already in progress");
}

void PacketFlowBase::startPacketStreaming(Packet *packet)
{
    inProgressStreamId = packet->getTreeId();
}

void PacketFlowBase::endPacketStreaming(Packet *packet)
{
    handlePacketProcessed(packet);
    inProgressStreamId = -1;
}

bool PacketFlowBase::canPushSomePacket(const cGate *gate) const
{
    return consumer == nullptr || consumer->canPushSomePacket(consumer.getReferencedGate());
}

bool PacketFlowBase::canPushPacket(Packet *packet, const cGate *gate) const
{
    return consumer == nullptr || consumer->canPushPacket(packet, consumer.getReferencedGate());
}

void PacketFlowBase::pushPacket(Packet *packet, const cGate *gate)
{
    Enter_Method("pushPacket");
    take(packet);
    checkPacketStreaming(nullptr);
    emit(packetPushedInSignal, packet);
    processPacket(packet);
    handlePacketProcessed(packet);
    emit(packetPushedOutSignal, packet);
    pushOrSendPacket(packet, outputGate, consumer.getReferencedGate(), consumer);
    updateDisplayString();
}

void PacketFlowBase::pushPacketStart(Packet *packet, const cGate *gate, bps datarate)
{
    Enter_Method("pushPacketStart");
    take(packet);
    checkPacketStreaming(packet);
    emit(packetPushedInSignal, packet);
    startPacketStreaming(packet);
    processPacket(packet);
    pushOrSendPacketStart(packet, outputGate, consumer.getReferencedGate(), consumer, datarate, packet->getTransmissionId());
    updateDisplayString();
}

void PacketFlowBase::pushPacketEnd(Packet *packet, const cGate *gate)
{
    Enter_Method("pushPacketEnd");
    take(packet);
    if (!isStreamingPacket())
        startPacketStreaming(packet);
    else
        checkPacketStreaming(packet);
    processPacket(packet);
    emit(packetPushedOutSignal, packet);
    endPacketStreaming(packet);
    pushOrSendPacketEnd(packet, outputGate, consumer.getReferencedGate(), consumer, packet->getTransmissionId());
    updateDisplayString();
}

void PacketFlowBase::pushPacketProgress(Packet *packet, const cGate *gate, bps datarate, b position, b extraProcessableLength)
{
    Enter_Method("pushPacketProgress");
    take(packet);
    if (!isStreamingPacket())
        startPacketStreaming(packet);
    else
        checkPacketStreaming(packet);
    bool isPacketEnd = packet->getTotalLength() == position + extraProcessableLength;
    processPacket(packet);
    if (isPacketEnd) {
        emit(packetPushedOutSignal, packet);
        endPacketStreaming(packet);
        pushOrSendPacketEnd(packet, outputGate, consumer.getReferencedGate(), consumer, packet->getTransmissionId());
    }
    else
        pushOrSendPacketProgress(packet, outputGate, consumer.getReferencedGate(), consumer, datarate, position, extraProcessableLength, packet->getTransmissionId());
    updateDisplayString();
}

void PacketFlowBase::handleCanPushPacketChanged(const cGate *gate)
{
    Enter_Method("handleCanPushPacketChanged");
    if (producer != nullptr)
        producer->handleCanPushPacketChanged(producer.getReferencedGate());
}

void PacketFlowBase::handlePushPacketProcessed(Packet *packet, const cGate *gate, bool successful)
{
    Enter_Method("handlePushPacketProcessed");
    endPacketStreaming(packet);
    if (producer != nullptr)
        producer->handlePushPacketProcessed(packet, producer.getReferencedGate(), successful);
}

bool PacketFlowBase::canPullSomePacket(const cGate *gate) const
{
    return provider != nullptr && provider->canPullSomePacket(provider.getReferencedGate());
}

Packet *PacketFlowBase::canPullPacket(const cGate *gate) const
{
    return provider != nullptr ? provider->canPullPacket(provider.getReferencedGate()) : nullptr;
}

Packet *PacketFlowBase::pullPacket(const cGate *gate)
{
    Enter_Method("pullPacket");
    checkPacketStreaming(nullptr);
    auto packet = provider->pullPacket(provider.getReferencedGate());
    take(packet);
    emit(packetPulledInSignal, packet);
    processPacket(packet);
    handlePacketProcessed(packet);
    emit(packetPulledOutSignal, packet);
    animatePullPacket(packet, outputGate, findConnectedGate<IActivePacketSink>(outputGate));
    updateDisplayString();
    return packet;
}

Packet *PacketFlowBase::pullPacketStart(const cGate *gate, bps datarate)
{
    Enter_Method("pullPacketStart");
    checkPacketStreaming(nullptr);
    auto packet = provider->pullPacketStart(provider.getReferencedGate(), datarate);
    take(packet);
    emit(packetPulledInSignal, packet);
    inProgressStreamId = packet->getTreeId();
    processPacket(packet);
    emit(packetPulledOutSignal, packet);
    animatePullPacketStart(packet, outputGate, findConnectedGate<IActivePacketSink>(outputGate), datarate, packet->getTransmissionId());
    updateDisplayString();
    return packet;
}

Packet *PacketFlowBase::pullPacketEnd(const cGate *gate)
{
    Enter_Method("pullPacketEnd");
    auto packet = provider->pullPacketEnd(provider.getReferencedGate());
    take(packet);
    checkPacketStreaming(packet);
    emit(packetPulledInSignal, packet);
    processPacket(packet);
    inProgressStreamId = packet->getTreeId();
    emit(packetPulledOutSignal, packet);
    endPacketStreaming(packet);
    animatePullPacketEnd(packet, outputGate, findConnectedGate<IActivePacketSink>(outputGate), packet->getTransmissionId());
    updateDisplayString();
    return packet;
}

Packet *PacketFlowBase::pullPacketProgress(const cGate *gate, bps datarate, b position, b extraProcessableLength)
{
    Enter_Method("pullPacketProgress");
    auto packet = provider->pullPacketProgress(provider.getReferencedGate(), datarate, position, extraProcessableLength);
    take(packet);
    checkPacketStreaming(packet);
    inProgressStreamId = packet->getTreeId();
    bool isPacketEnd = packet->getTotalLength() == position + extraProcessableLength;
    processPacket(packet);
    if (isPacketEnd) {
        emit(packetPulledOutSignal, packet);
        endPacketStreaming(packet);
    }
    animatePullPacketProgress(packet, outputGate, findConnectedGate<IActivePacketSink>(outputGate), datarate, position, extraProcessableLength, packet->getTransmissionId());
    updateDisplayString();
    return packet;
}

void PacketFlowBase::handleCanPullPacketChanged(const cGate *gate)
{
    Enter_Method("handleCanPullPacketChanged");
    if (collector != nullptr)
        collector->handleCanPullPacketChanged(collector.getReferencedGate());
}

void PacketFlowBase::handlePullPacketProcessed(Packet *packet, const cGate *gate, bool successful)
{
    Enter_Method("handlePullPacketProcessed");
    endPacketStreaming(packet);
    if (collector != nullptr)
        collector->handlePullPacketProcessed(packet, collector.getReferencedGate(), successful);
}

} // namespace queueing
} // namespace inet

