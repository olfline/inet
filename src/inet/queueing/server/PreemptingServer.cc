//
// Copyright (C) 2020 OpenSim Ltd.
//
// SPDX-License-Identifier: LGPL-3.0-or-later
//


#include "inet/queueing/server/PreemptingServer.h"

namespace inet {
namespace queueing {

Define_Module(PreemptingServer);

void PreemptingServer::initialize(int stage)
{
    ClockUserModuleMixin::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        datarate = bps(par("datarate"));
        timer = new ClockEvent("Timer");
    }
}

void PreemptingServer::handleMessage(cMessage *message)
{
    if (message == timer)
        endStreaming();
    else
        PacketServerBase::handleMessage(message);
}

bool PreemptingServer::canStartStreaming() const
{
    return provider->canPullSomePacket(provider.getReferencedGate()) && consumer->canPushSomePacket(consumer.getReferencedGate());
}

void PreemptingServer::startStreaming()
{
    auto packet = provider->pullPacketStart(provider.getReferencedGate(), datarate);
    take(packet);
    EV_INFO << "Starting streaming packet" << EV_FIELD(packet) << EV_ENDL;
    streamedPacket = packet;
    pushOrSendPacketStart(streamedPacket->dup(), outputGate, consumer.getReferencedGate(), consumer, datarate, packet->getTransmissionId());
    scheduleClockEventAfter(s(streamedPacket->getTotalLength() / datarate).get(), timer);
    handlePacketProcessed(streamedPacket);
    updateDisplayString();
}

void PreemptingServer::endStreaming()
{
    auto packet = provider->pullPacketEnd(provider.getReferencedGate());
    take(packet);
    delete streamedPacket;
    streamedPacket = packet;
    EV_INFO << "Ending streaming packet" << EV_FIELD(packet, *streamedPacket) << EV_ENDL;
    pushOrSendPacketEnd(streamedPacket, outputGate, consumer.getReferencedGate(), consumer, packet->getTransmissionId());
    streamedPacket = nullptr;
    updateDisplayString();
}

void PreemptingServer::handleCanPushPacketChanged(const cGate *gate)
{
    Enter_Method("handleCanPushPacketChanged");
    if (!isStreaming() && canStartStreaming())
        startStreaming();
}

void PreemptingServer::handleCanPullPacketChanged(const cGate *gate)
{
    Enter_Method("handleCanPullPacketChanged");
    if (isStreaming()) {
        endStreaming();
        cancelClockEvent(timer);
    }
    else if (canStartStreaming())
        startStreaming();
}

void PreemptingServer::handlePushPacketProcessed(Packet *packet, const cGate *gate, bool successful)
{
    Enter_Method("handlePushPacketProcessed");
    if (isStreaming()) {
        delete streamedPacket;
        streamedPacket = provider->pullPacketEnd(provider.getReferencedGate());
        take(streamedPacket);
        EV_INFO << "Ending streaming packet" << EV_FIELD(packet, *streamedPacket) << EV_ENDL;
        delete streamedPacket;
        streamedPacket = nullptr;
    }
}

} // namespace queueing
} // namespace inet

