//
// Copyright (C) 2013 OpenSim Ltd.
//
// SPDX-License-Identifier: LGPL-3.0-or-later
//


#include "inet/physicallayer/wireless/common/analogmodel/packetlevel/DimensionalAnalogModel.h"

#include "inet/physicallayer/wireless/common/analogmodel/packetlevel/DimensionalNoise.h"
#include "inet/physicallayer/wireless/common/analogmodel/bitlevel/DimensionalSignalAnalogModel.h"
#include "inet/physicallayer/wireless/common/analogmodel/packetlevel/DimensionalSnir.h"
#include "inet/physicallayer/wireless/common/analogmodel/bitlevel/DimensionalSignalAnalogModel.h"
#include "inet/physicallayer/wireless/common/radio/packetlevel/Reception.h"
#include "inet/physicallayer/wireless/common/contract/packetlevel/IRadioMedium.h"
#include "inet/physicallayer/wireless/common/radio/packetlevel/BandListening.h"

namespace inet {

namespace physicallayer {

Define_Module(DimensionalAnalogModel);

std::ostream& DimensionalAnalogModel::printToStream(std::ostream& stream, int level, int evFlags) const
{
    stream << "DimensionalAnalogModel";
    return DimensionalAnalogModelBase::printToStream(stream, level);
}

const IReception *DimensionalAnalogModel::computeReception(const IRadio *receiverRadio, const ITransmission *transmission, const IArrival *arrival) const
{
    auto dimensionalTransmission = check_and_cast<const DimensionalSignalAnalogModel *>(transmission->getAnalogModel());
    const simtime_t receptionStartTime = arrival->getStartTime();
    const simtime_t receptionEndTime = arrival->getEndTime();
    const Coord& receptionStartPosition = arrival->getStartPosition();
    const Coord& receptionEndPosition = arrival->getEndPosition();
    const Quaternion& receptionStartOrientation = arrival->getStartOrientation();
    const Quaternion& receptionEndOrientation = arrival->getEndOrientation();
    const Ptr<const IFunction<WpHz, Domain<simsec, Hz>>>& receptionPower = computeReceptionPower(receiverRadio, transmission, arrival);
    // KLUDGE TODO
    auto reception = new Reception(nullptr, receiverRadio, transmission, receptionStartTime, receptionEndTime, receptionStartPosition, receptionEndPosition, receptionStartOrientation, receptionEndOrientation);
    reception->analogModel = new DimensionalReceptionSignalAnalogModel(-1, -1, -1, dimensionalTransmission->getCenterFrequency(), dimensionalTransmission->getBandwidth(), receptionPower);
    return reception;
}

} // namespace physicallayer

} // namespace inet

