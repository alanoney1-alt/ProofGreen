import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../utils/api';
import debounce from 'lodash/debounce';

/**
 * Equipment Lookup Component
 * Search and select equipment from database or scan model number
 */
const EquipmentLookup = ({ category, value, onChange }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedEquipment, setSelectedEquipment] = useState(value);
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [manualData, setManualData] = useState({});

  // Debounced search
  const searchEquipment = useCallback(
    debounce(async (query) => {
      if (query.length < 2) {
        setSearchResults([]);
        return;
      }

      try {
        setLoading(true);
        const params = new URLSearchParams({ q: query, limit: 10 });
        if (category) params.append('category', category);

        const response = await api.get(`/data/equipment/search?${params}`);
        if (response.success) {
          setSearchResults(response.equipment);
        }
      } catch (error) {
        console.error('Equipment search error:', error);
      } finally {
        setLoading(false);
      }
    }, 300),
    [category]
  );

  useEffect(() => {
    searchEquipment(searchQuery);
  }, [searchQuery, searchEquipment]);

  // Handle equipment selection
  const handleSelect = (equipment) => {
    setSelectedEquipment(equipment);
    onChange(equipment);
    setSearchQuery('');
    setSearchResults([]);
  };

  // Handle manual entry
  const handleManualSave = () => {
    const equipment = {
      ...manualData,
      isManualEntry: true
    };
    setSelectedEquipment(equipment);
    onChange(equipment);
    setShowManualEntry(false);
  };

  // Clear selection
  const handleClear = () => {
    setSelectedEquipment(null);
    onChange(null);
  };

  return (
    <div className="space-y-3">
      {/* Selected equipment display */}
      {selectedEquipment && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <div className="flex justify-between items-start">
            <div>
              <p className="font-medium text-green-900">
                {selectedEquipment.model_name || selectedEquipment.custom_model || 'Custom Equipment'}
              </p>
              <p className="text-sm text-green-700">
                {selectedEquipment.manufacturer?.name || selectedEquipment.custom_make} - {selectedEquipment.model_number || 'N/A'}
              </p>
              {selectedEquipment.refrigerant_type && (
                <p className="text-xs text-green-600 mt-1">
                  Refrigerant: {selectedEquipment.refrigerant_type} | GWP: {selectedEquipment.gwp_value}
                </p>
              )}
              {selectedEquipment.seer_rating && (
                <p className="text-xs text-green-600">
                  SEER: {selectedEquipment.seer_rating} | {selectedEquipment.energy_star_certified ? '★ ENERGY STAR' : ''}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={handleClear}
              className="text-green-600 hover:text-green-800"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Search input */}
      {!selectedEquipment && !showManualEntry && (
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by model number or name..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
          />
          {loading && (
            <div className="absolute right-3 top-2.5">
              <div className="animate-spin h-5 w-5 border-2 border-green-600 border-t-transparent rounded-full"></div>
            </div>
          )}

          {/* Search results dropdown */}
          {searchResults.length > 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
              {searchResults.map((equipment) => (
                <button
                  key={equipment.id}
                  type="button"
                  onClick={() => handleSelect(equipment)}
                  className="w-full px-3 py-2 text-left hover:bg-green-50 border-b border-gray-100 last:border-0"
                >
                  <p className="font-medium text-gray-900">
                    {equipment.model_name || equipment.model_number}
                  </p>
                  <p className="text-sm text-gray-600">
                    {equipment.manufacturer?.name} | {equipment.model_number}
                  </p>
                  {equipment.seer_rating && (
                    <span className="inline-block mt-1 px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">
                      SEER {equipment.seer_rating}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* No results / manual entry option */}
          {searchQuery.length >= 2 && !loading && searchResults.length === 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
              <p className="text-gray-500 text-sm mb-2">No equipment found</p>
              <button
                type="button"
                onClick={() => setShowManualEntry(true)}
                className="text-green-600 hover:text-green-800 text-sm font-medium"
              >
                + Enter equipment manually
              </button>
            </div>
          )}
        </div>
      )}

      {/* Manual entry toggle */}
      {!selectedEquipment && !showManualEntry && (
        <button
          type="button"
          onClick={() => setShowManualEntry(true)}
          className="text-sm text-gray-500 hover:text-green-600"
        >
          Can't find equipment? Enter manually
        </button>
      )}

      {/* Manual entry form */}
      {showManualEntry && (
        <div className="border border-gray-200 rounded-lg p-4 space-y-3">
          <h4 className="font-medium text-gray-900">Manual Equipment Entry</h4>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Make/Brand</label>
              <input
                type="text"
                value={manualData.custom_make || ''}
                onChange={(e) => setManualData({ ...manualData, custom_make: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Model Number</label>
              <input
                type="text"
                value={manualData.custom_model || ''}
                onChange={(e) => setManualData({ ...manualData, custom_model: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Serial Number</label>
              <input
                type="text"
                value={manualData.serial_number || ''}
                onChange={(e) => setManualData({ ...manualData, serial_number: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">SEER Rating</label>
              <input
                type="number"
                value={manualData.seer_rating || ''}
                onChange={(e) => setManualData({ ...manualData, seer_rating: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
                step="0.5"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Refrigerant Type</label>
              <input
                type="text"
                value={manualData.refrigerant_type || ''}
                onChange={(e) => setManualData({ ...manualData, refrigerant_type: e.target.value })}
                placeholder="e.g., R-410A"
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tonnage/Capacity</label>
              <input
                type="text"
                value={manualData.tonnage || ''}
                onChange={(e) => setManualData({ ...manualData, tonnage: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
          </div>

          <div className="flex items-center space-x-2 pt-2">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={manualData.energy_star || false}
                onChange={(e) => setManualData({ ...manualData, energy_star: e.target.checked })}
                className="rounded text-green-600"
              />
              <span className="text-sm">ENERGY STAR Certified</span>
            </label>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={() => setShowManualEntry(false)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleManualSave}
              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700"
            >
              Save Equipment
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default EquipmentLookup;
