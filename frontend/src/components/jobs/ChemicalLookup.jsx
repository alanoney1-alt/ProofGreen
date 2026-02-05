import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../utils/api';
import debounce from 'lodash/debounce';

/**
 * Chemical Lookup Component
 * Search chemicals by name or EPA registration number
 */
const ChemicalLookup = ({ value, onChange, multiple = false }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedChemicals, setSelectedChemicals] = useState(multiple ? (value || []) : (value ? [value] : []));
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [manualData, setManualData] = useState({});
  const [quantityInputs, setQuantityInputs] = useState({});

  // Debounced search
  const searchChemicals = useCallback(
    debounce(async (query) => {
      if (query.length < 2) {
        setSearchResults([]);
        return;
      }

      try {
        setLoading(true);
        const response = await api.get(`/data/chemicals/search?q=${encodeURIComponent(query)}&limit=10`);
        if (response.success) {
          setSearchResults(response.chemicals);
        }
      } catch (error) {
        console.error('Chemical search error:', error);
      } finally {
        setLoading(false);
      }
    }, 300),
    []
  );

  useEffect(() => {
    searchChemicals(searchQuery);
  }, [searchQuery, searchChemicals]);

  // Handle chemical selection
  const handleSelect = (chemical) => {
    if (multiple) {
      const exists = selectedChemicals.find(c => c.id === chemical.id);
      if (!exists) {
        const updated = [...selectedChemicals, { ...chemical, quantity: 0, unit: 'oz' }];
        setSelectedChemicals(updated);
        onChange(updated);
      }
    } else {
      setSelectedChemicals([chemical]);
      onChange(chemical);
    }
    setSearchQuery('');
    setSearchResults([]);
  };

  // Handle quantity change
  const handleQuantityChange = (chemicalId, quantity, unit) => {
    const updated = selectedChemicals.map(c =>
      c.id === chemicalId ? { ...c, quantity: parseFloat(quantity) || 0, unit } : c
    );
    setSelectedChemicals(updated);
    onChange(multiple ? updated : updated[0]);
  };

  // Remove chemical
  const handleRemove = (chemicalId) => {
    const updated = selectedChemicals.filter(c => c.id !== chemicalId);
    setSelectedChemicals(updated);
    onChange(multiple ? updated : null);
  };

  // Handle manual entry
  const handleManualSave = () => {
    const chemical = {
      ...manualData,
      id: `manual_${Date.now()}`,
      isManualEntry: true,
      quantity: 0,
      unit: 'oz'
    };

    if (multiple) {
      const updated = [...selectedChemicals, chemical];
      setSelectedChemicals(updated);
      onChange(updated);
    } else {
      setSelectedChemicals([chemical]);
      onChange(chemical);
    }
    setShowManualEntry(false);
    setManualData({});
  };

  // Get signal word color
  const getSignalWordColor = (signalWord) => {
    switch (signalWord?.toLowerCase()) {
      case 'danger': return 'bg-red-100 text-red-700';
      case 'warning': return 'bg-yellow-100 text-yellow-700';
      case 'caution': return 'bg-blue-100 text-blue-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="space-y-3">
      {/* Selected chemicals display */}
      {selectedChemicals.length > 0 && (
        <div className="space-y-2">
          {selectedChemicals.map((chemical) => (
            <div key={chemical.id} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-gray-900">{chemical.name}</p>
                    {chemical.signal_word && (
                      <span className={`px-2 py-0.5 text-xs rounded ${getSignalWordColor(chemical.signal_word)}`}>
                        {chemical.signal_word}
                      </span>
                    )}
                    {chemical.organic_certified && (
                      <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                        Organic
                      </span>
                    )}
                  </div>
                  {chemical.epa_registration_number && (
                    <p className="text-sm text-gray-600">EPA Reg #: {chemical.epa_registration_number}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => handleRemove(chemical.id)}
                  className="text-gray-400 hover:text-red-500"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Quantity inputs */}
              <div className="flex items-center gap-2 mt-2">
                <label className="text-sm text-gray-500">Amount:</label>
                <input
                  type="number"
                  value={chemical.quantity || ''}
                  onChange={(e) => handleQuantityChange(chemical.id, e.target.value, chemical.unit)}
                  className="w-20 px-2 py-1 border border-gray-300 rounded text-sm"
                  min="0"
                  step="0.1"
                />
                <select
                  value={chemical.unit || 'oz'}
                  onChange={(e) => handleQuantityChange(chemical.id, chemical.quantity, e.target.value)}
                  className="px-2 py-1 border border-gray-300 rounded text-sm"
                >
                  <option value="oz">oz</option>
                  <option value="gal">gal</option>
                  <option value="lb">lb</option>
                  <option value="ml">ml</option>
                  <option value="L">L</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Search input */}
      {(multiple || selectedChemicals.length === 0) && !showManualEntry && (
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by product name or EPA registration #..."
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
              {searchResults.map((chemical) => (
                <button
                  key={chemical.id}
                  type="button"
                  onClick={() => handleSelect(chemical)}
                  className="w-full px-3 py-2 text-left hover:bg-green-50 border-b border-gray-100 last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-gray-900">{chemical.name}</p>
                    {chemical.signal_word && (
                      <span className={`px-2 py-0.5 text-xs rounded ${getSignalWordColor(chemical.signal_word)}`}>
                        {chemical.signal_word}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600">
                    {chemical.epa_registration_number && `EPA #${chemical.epa_registration_number}`}
                    {chemical.category && ` • ${chemical.category}`}
                  </p>
                  {chemical.organic_certified && (
                    <span className="inline-block mt-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                      Organic Certified
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* No results */}
          {searchQuery.length >= 2 && !loading && searchResults.length === 0 && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-3">
              <p className="text-gray-500 text-sm mb-2">No chemicals found</p>
              <button
                type="button"
                onClick={() => setShowManualEntry(true)}
                className="text-green-600 hover:text-green-800 text-sm font-medium"
              >
                + Enter chemical manually
              </button>
            </div>
          )}
        </div>
      )}

      {/* Manual entry toggle */}
      {(multiple || selectedChemicals.length === 0) && !showManualEntry && (
        <button
          type="button"
          onClick={() => setShowManualEntry(true)}
          className="text-sm text-gray-500 hover:text-green-600"
        >
          Can't find product? Enter manually
        </button>
      )}

      {/* Manual entry form */}
      {showManualEntry && (
        <div className="border border-gray-200 rounded-lg p-4 space-y-3">
          <h4 className="font-medium text-gray-900">Manual Chemical Entry</h4>

          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Product Name *</label>
              <input
                type="text"
                value={manualData.name || ''}
                onChange={(e) => setManualData({ ...manualData, name: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">EPA Registration #</label>
              <input
                type="text"
                value={manualData.epa_registration_number || ''}
                onChange={(e) => setManualData({ ...manualData, epa_registration_number: e.target.value })}
                placeholder="e.g., 7969-210"
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Category</label>
              <select
                value={manualData.category || ''}
                onChange={(e) => setManualData({ ...manualData, category: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              >
                <option value="">Select...</option>
                <option value="insecticide">Insecticide</option>
                <option value="termiticide">Termiticide</option>
                <option value="herbicide">Herbicide</option>
                <option value="fungicide">Fungicide</option>
                <option value="rodenticide">Rodenticide</option>
                <option value="disinfectant">Disinfectant</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Signal Word</label>
              <select
                value={manualData.signal_word || ''}
                onChange={(e) => setManualData({ ...manualData, signal_word: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              >
                <option value="">Select...</option>
                <option value="Danger">Danger</option>
                <option value="Warning">Warning</option>
                <option value="Caution">Caution</option>
                <option value="None">None</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Active Ingredient</label>
              <input
                type="text"
                value={manualData.active_ingredient || ''}
                onChange={(e) => setManualData({ ...manualData, active_ingredient: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              />
            </div>
          </div>

          <div className="flex items-center space-x-4 pt-2">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={manualData.organic_certified || false}
                onChange={(e) => setManualData({ ...manualData, organic_certified: e.target.checked })}
                className="rounded text-green-600"
              />
              <span className="text-sm">Organic Certified</span>
            </label>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={manualData.pollinator_safe || false}
                onChange={(e) => setManualData({ ...manualData, pollinator_safe: e.target.checked })}
                className="rounded text-green-600"
              />
              <span className="text-sm">Pollinator Safe</span>
            </label>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={() => {
                setShowManualEntry(false);
                setManualData({});
              }}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleManualSave}
              disabled={!manualData.name}
              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:bg-gray-300"
            >
              Add Chemical
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChemicalLookup;
