import React, { useState, useEffect } from 'react';
import { api } from '../../utils/api';

/**
 * Trip Calculator Component
 * Calculate mileage and emissions for service trips
 */
const TripCalculator = ({ companyId, jobId, onChange }) => {
  const [trips, setTrips] = useState([{
    id: 1,
    vehicleType: 'van',
    fuelType: 'gasoline',
    distanceMiles: '',
    mpg: ''
  }]);
  const [calculations, setCalculations] = useState(null);
  const [loading, setLoading] = useState(false);
  const [emissionFactors, setEmissionFactors] = useState(null);
  const [useManualMileage, setUseManualMileage] = useState(true);

  // Load emission factors
  useEffect(() => {
    const loadFactors = async () => {
      try {
        const response = await api.get('/data/trips/emission-factors');
        if (response.success) {
          setEmissionFactors(response);
        }
      } catch (error) {
        console.error('Failed to load emission factors:', error);
      }
    };
    loadFactors();
  }, []);

  const vehicleTypes = [
    { value: 'car', label: 'Car/Sedan' },
    { value: 'van', label: 'Service Van' },
    { value: 'pickup', label: 'Pickup Truck' },
    { value: 'box_truck_16ft', label: '16ft Box Truck' },
    { value: 'box_truck_20ft', label: '20ft Box Truck' },
    { value: 'box_truck_26ft', label: '26ft Box Truck' },
    { value: 'semi', label: 'Semi Truck' }
  ];

  const fuelTypes = [
    { value: 'gasoline', label: 'Gasoline' },
    { value: 'diesel', label: 'Diesel' },
    { value: 'electric', label: 'Electric' },
    { value: 'hybrid', label: 'Hybrid' },
    { value: 'cng', label: 'CNG' }
  ];

  // Add trip
  const handleAddTrip = () => {
    setTrips(prev => [...prev, {
      id: Date.now(),
      vehicleType: 'van',
      fuelType: 'gasoline',
      distanceMiles: '',
      mpg: ''
    }]);
  };

  // Remove trip
  const handleRemoveTrip = (tripId) => {
    if (trips.length > 1) {
      setTrips(prev => prev.filter(t => t.id !== tripId));
    }
  };

  // Update trip
  const handleTripChange = (tripId, field, value) => {
    setTrips(prev => prev.map(t =>
      t.id === tripId ? { ...t, [field]: value } : t
    ));
  };

  // Calculate emissions
  const handleCalculate = async () => {
    const validTrips = trips.filter(t => t.distanceMiles && parseFloat(t.distanceMiles) > 0);

    if (validTrips.length === 0) {
      return;
    }

    setLoading(true);

    try {
      const tripData = validTrips.map(t => ({
        distanceMiles: parseFloat(t.distanceMiles),
        vehicleType: t.vehicleType,
        fuelType: t.fuelType,
        mpg: t.mpg ? parseFloat(t.mpg) : null
      }));

      const response = await api.post('/data/trips/calculate-job', { trips: tripData });

      if (response.success) {
        setCalculations(response);

        if (onChange) {
          onChange({
            trips: response.trips,
            totals: response.totals,
            offset: response.offset
          });
        }
      }
    } catch (error) {
      console.error('Calculation error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Get default MPG for vehicle/fuel combo
  const getDefaultMpg = (vehicleType, fuelType) => {
    return emissionFactors?.defaultMPG?.[vehicleType]?.[fuelType] || '';
  };

  return (
    <div className="space-y-4">
      {/* Trips list */}
      {trips.map((trip, index) => (
        <div key={trip.id} className="border border-gray-200 rounded-lg p-4">
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-medium text-gray-700">
              Trip {index + 1}
            </span>
            {trips.length > 1 && (
              <button
                type="button"
                onClick={() => handleRemoveTrip(trip.id)}
                className="text-gray-400 hover:text-red-500"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Vehicle Type</label>
              <select
                value={trip.vehicleType}
                onChange={(e) => handleTripChange(trip.id, 'vehicleType', e.target.value)}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              >
                {vehicleTypes.map(vt => (
                  <option key={vt.value} value={vt.value}>{vt.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Fuel Type</label>
              <select
                value={trip.fuelType}
                onChange={(e) => handleTripChange(trip.id, 'fuelType', e.target.value)}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              >
                {fuelTypes.map(ft => (
                  <option key={ft.value} value={ft.value}>{ft.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Distance (miles)</label>
              <input
                type="number"
                value={trip.distanceMiles}
                onChange={(e) => handleTripChange(trip.id, 'distanceMiles', e.target.value)}
                placeholder="0"
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                min="0"
                step="0.1"
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                MPG <span className="text-gray-400">(optional)</span>
              </label>
              <input
                type="number"
                value={trip.mpg}
                onChange={(e) => handleTripChange(trip.id, 'mpg', e.target.value)}
                placeholder={getDefaultMpg(trip.vehicleType, trip.fuelType) || 'Default'}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                min="1"
                step="0.1"
              />
            </div>
          </div>
        </div>
      ))}

      {/* Add trip button */}
      <button
        type="button"
        onClick={handleAddTrip}
        className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-gray-500 hover:border-green-400 hover:text-green-600 transition-colors"
      >
        + Add Another Trip
      </button>

      {/* Calculate button */}
      <button
        type="button"
        onClick={handleCalculate}
        disabled={loading || !trips.some(t => t.distanceMiles)}
        className="w-full py-2 px-4 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 font-medium flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
            Calculating...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            Calculate Emissions
          </>
        )}
      </button>

      {/* Results */}
      {calculations && (
        <div className="bg-gray-50 rounded-lg p-4 space-y-4">
          <h4 className="font-medium text-gray-900">Emissions Summary</h4>

          {/* Individual trips */}
          <div className="space-y-2">
            {calculations.trips?.map((trip, index) => (
              <div key={index} className="flex justify-between text-sm py-2 border-b border-gray-200">
                <span className="text-gray-600">
                  Trip {index + 1}: {trip.distanceMiles} mi ({trip.vehicleType}, {trip.fuelType})
                </span>
                <span className="font-medium text-gray-900">
                  {trip.co2EmissionsLbs} lbs CO₂
                </span>
              </div>
            ))}
          </div>

          {/* Totals */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {calculations.totals?.distanceMiles}
                </p>
                <p className="text-sm text-gray-500">Total Miles</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">
                  {calculations.totals?.fuelUsedGallons}
                </p>
                <p className="text-sm text-gray-500">Gallons Fuel</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">
                  {calculations.totals?.co2EmissionsLbs}
                </p>
                <p className="text-sm text-gray-500">lbs CO₂</p>
              </div>
            </div>
          </div>

          {/* Carbon offset info */}
          {calculations.offset && (
            <div className="bg-green-50 rounded-lg p-4 border border-green-200">
              <h5 className="font-medium text-green-800 mb-2">Carbon Offset Options</h5>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-green-600">CO₂ in tons:</p>
                  <p className="font-medium text-green-800">{calculations.offset.co2Tons} tons</p>
                </div>
                <div>
                  <p className="text-green-600">Offset cost range:</p>
                  <p className="font-medium text-green-800">
                    ${calculations.offset.offsetCostRange?.low} - ${calculations.offset.offsetCostRange?.high}
                  </p>
                </div>
                <div className="col-span-2">
                  <p className="text-green-600">Trees equivalent (annual absorption):</p>
                  <p className="font-medium text-green-800">
                    {calculations.offset.treesEquivalent} trees
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Emission factors reference */}
      {emissionFactors && (
        <details className="text-sm">
          <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
            View emission factors
          </summary>
          <div className="mt-2 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs text-gray-500 mb-2">lbs CO₂ per gallon of fuel:</p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              {Object.entries(emissionFactors.fuelEmissionFactors || {}).map(([fuel, factor]) => (
                <div key={fuel} className="flex justify-between">
                  <span className="capitalize">{fuel}:</span>
                  <span className="font-medium">{factor}</span>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}
    </div>
  );
};

export default TripCalculator;
