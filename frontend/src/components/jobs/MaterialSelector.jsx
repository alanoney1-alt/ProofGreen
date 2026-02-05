import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../utils/api';
import debounce from 'lodash/debounce';

/**
 * Material Selector Component
 * Search and select materials with quantities
 */
const MaterialSelector = ({ categories, value, onChange }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedMaterials, setSelectedMaterials] = useState(value || []);
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [manualData, setManualData] = useState({});
  const [activeCategory, setActiveCategory] = useState(categories?.[0] || 'all');

  // Debounced search
  const searchMaterials = useCallback(
    debounce(async (query, category) => {
      if (query.length < 2) {
        setSearchResults([]);
        return;
      }

      try {
        setLoading(true);
        const params = new URLSearchParams({ q: query, limit: 15 });
        if (category && category !== 'all') {
          params.append('category', category);
        }

        const response = await api.get(`/data/materials/search?${params}`);
        if (response.success) {
          setSearchResults(response.materials);
        }
      } catch (error) {
        console.error('Material search error:', error);
      } finally {
        setLoading(false);
      }
    }, 300),
    []
  );

  useEffect(() => {
    if (searchQuery) {
      searchMaterials(searchQuery, activeCategory);
    }
  }, [searchQuery, activeCategory, searchMaterials]);

  // Handle material selection
  const handleSelect = (material) => {
    const exists = selectedMaterials.find(m => m.id === material.id);
    if (!exists) {
      const updated = [
        ...selectedMaterials,
        { ...material, quantity: 1, waste_lbs: 0, recycled_lbs: 0 }
      ];
      setSelectedMaterials(updated);
      onChange(updated);
    }
    setSearchQuery('');
    setSearchResults([]);
  };

  // Handle quantity/waste changes
  const handleMaterialUpdate = (materialId, field, value) => {
    const updated = selectedMaterials.map(m =>
      m.id === materialId ? { ...m, [field]: parseFloat(value) || 0 } : m
    );
    setSelectedMaterials(updated);
    onChange(updated);
  };

  // Remove material
  const handleRemove = (materialId) => {
    const updated = selectedMaterials.filter(m => m.id !== materialId);
    setSelectedMaterials(updated);
    onChange(updated);
  };

  // Handle manual entry
  const handleManualSave = () => {
    const material = {
      ...manualData,
      id: `manual_${Date.now()}`,
      isManualEntry: true,
      quantity: 1,
      waste_lbs: 0,
      recycled_lbs: 0
    };

    const updated = [...selectedMaterials, material];
    setSelectedMaterials(updated);
    onChange(updated);
    setShowManualEntry(false);
    setManualData({});
  };

  // Calculate totals
  const calculateTotals = () => {
    let totalCarbonKg = 0;
    let totalWasteLbs = 0;
    let totalRecycledLbs = 0;

    selectedMaterials.forEach(m => {
      if (m.embodied_carbon_kg_per_unit) {
        totalCarbonKg += m.embodied_carbon_kg_per_unit * (m.quantity || 0);
      }
      totalWasteLbs += m.waste_lbs || 0;
      totalRecycledLbs += m.recycled_lbs || 0;
    });

    return {
      carbonKg: totalCarbonKg.toFixed(2),
      carbonLbs: (totalCarbonKg * 2.205).toFixed(2),
      wasteLbs: totalWasteLbs.toFixed(2),
      recycledLbs: totalRecycledLbs.toFixed(2),
      recyclingRate: totalWasteLbs > 0 ? ((totalRecycledLbs / totalWasteLbs) * 100).toFixed(1) : 0
    };
  };

  const totals = calculateTotals();

  return (
    <div className="space-y-3">
      {/* Category tabs */}
      {categories && categories.length > 1 && (
        <div className="flex flex-wrap gap-1">
          <button
            type="button"
            onClick={() => setActiveCategory('all')}
            className={`px-3 py-1 text-xs rounded-full ${
              activeCategory === 'all'
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1 text-xs rounded-full capitalize ${
                activeCategory === cat
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {cat.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      )}

      {/* Search input */}
      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search materials by name..."
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
            {searchResults.map((material) => (
              <button
                key={material.id}
                type="button"
                onClick={() => handleSelect(material)}
                className="w-full px-3 py-2 text-left hover:bg-green-50 border-b border-gray-100 last:border-0"
              >
                <p className="font-medium text-gray-900">{material.name}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-500">{material.category}</span>
                  {material.recyclable && (
                    <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs rounded">
                      Recyclable
                    </span>
                  )}
                  {material.embodied_carbon_kg_per_unit && (
                    <span className="text-xs text-gray-400">
                      {material.embodied_carbon_kg_per_unit} kg CO₂/{material.unit_of_measure}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Selected materials */}
      {selectedMaterials.length > 0 && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-gray-600 font-medium">Material</th>
                <th className="px-3 py-2 text-center text-gray-600 font-medium w-24">Qty</th>
                <th className="px-3 py-2 text-center text-gray-600 font-medium w-24">Waste (lbs)</th>
                <th className="px-3 py-2 text-center text-gray-600 font-medium w-24">Recycled</th>
                <th className="px-3 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {selectedMaterials.map((material) => (
                <tr key={material.id} className="border-t border-gray-100">
                  <td className="px-3 py-2">
                    <p className="font-medium text-gray-900">{material.name}</p>
                    <p className="text-xs text-gray-500">
                      {material.unit_of_measure}
                      {material.embodied_carbon_kg_per_unit && (
                        <span className="ml-2 text-green-600">
                          {(material.embodied_carbon_kg_per_unit * (material.quantity || 0)).toFixed(2)} kg CO₂
                        </span>
                      )}
                    </p>
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={material.quantity || ''}
                      onChange={(e) => handleMaterialUpdate(material.id, 'quantity', e.target.value)}
                      className="w-full px-2 py-1 border border-gray-300 rounded text-center text-sm"
                      min="0"
                      step="0.1"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={material.waste_lbs || ''}
                      onChange={(e) => handleMaterialUpdate(material.id, 'waste_lbs', e.target.value)}
                      className="w-full px-2 py-1 border border-gray-300 rounded text-center text-sm"
                      min="0"
                      step="0.1"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={material.recycled_lbs || ''}
                      onChange={(e) => handleMaterialUpdate(material.id, 'recycled_lbs', e.target.value)}
                      className="w-full px-2 py-1 border border-gray-300 rounded text-center text-sm"
                      min="0"
                      step="0.1"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => handleRemove(material.id)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Totals row */}
          <div className="bg-gray-50 px-3 py-2 border-t border-gray-200">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">
                <strong>Embodied Carbon:</strong> {totals.carbonLbs} lbs CO₂
              </span>
              <span className="text-gray-600">
                <strong>Waste:</strong> {totals.wasteLbs} lbs
              </span>
              <span className="text-gray-600">
                <strong>Recycled:</strong> {totals.recycledLbs} lbs ({totals.recyclingRate}%)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Manual entry toggle */}
      <button
        type="button"
        onClick={() => setShowManualEntry(true)}
        className="text-sm text-gray-500 hover:text-green-600"
      >
        + Add custom material
      </button>

      {/* Manual entry form */}
      {showManualEntry && (
        <div className="border border-gray-200 rounded-lg p-4 space-y-3">
          <h4 className="font-medium text-gray-900">Add Custom Material</h4>

          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Material Name *</label>
              <input
                type="text"
                value={manualData.name || ''}
                onChange={(e) => setManualData({ ...manualData, name: e.target.value })}
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
                <option value="pipe">Pipe</option>
                <option value="wire">Wire</option>
                <option value="hvac">HVAC</option>
                <option value="insulation">Insulation</option>
                <option value="fixture">Fixture</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Unit of Measure</label>
              <select
                value={manualData.unit_of_measure || ''}
                onChange={(e) => setManualData({ ...manualData, unit_of_measure: e.target.value })}
                className="w-full px-2 py-1.5 border border-gray-300 rounded text-sm"
              >
                <option value="">Select...</option>
                <option value="ft">Feet</option>
                <option value="sqft">Square Feet</option>
                <option value="each">Each</option>
                <option value="lb">Pounds</option>
                <option value="gal">Gallons</option>
              </select>
            </div>
          </div>

          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={manualData.recyclable || false}
              onChange={(e) => setManualData({ ...manualData, recyclable: e.target.checked })}
              className="rounded text-green-600"
            />
            <span className="text-sm">Recyclable Material</span>
          </label>

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
              Add Material
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default MaterialSelector;
