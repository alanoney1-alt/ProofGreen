/**
 * ProofGreen AI Review Interface
 *
 * CRITICAL COMPONENT: All AI analyses MUST be reviewed and verified by users
 * before data is saved. This component ensures:
 * - Users see AI confidence level
 * - Users can modify/correct AI suggestions
 * - Users MUST enter actual weight from documentation
 * - Users MUST confirm legal attestation
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';

// Confidence level styling configurations
const CONFIDENCE_STYLES = {
  high: {
    bg: 'bg-green-50',
    border: 'border-green-500',
    text: 'text-green-800',
    icon: 'check-circle',
    iconColor: 'text-green-600'
  },
  medium: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-500',
    text: 'text-yellow-800',
    icon: 'exclamation-triangle',
    iconColor: 'text-yellow-600'
  },
  low: {
    bg: 'bg-red-50',
    border: 'border-red-500',
    text: 'text-red-800',
    icon: 'x-circle',
    iconColor: 'text-red-600'
  }
};

// Category options for manual additions
const CATEGORIES = [
  { value: 'furniture', label: 'Furniture' },
  { value: 'electronics', label: 'Electronics' },
  { value: 'metal', label: 'Metal' },
  { value: 'construction', label: 'Construction' },
  { value: 'hvac', label: 'HVAC' },
  { value: 'roofing', label: 'Roofing' },
  { value: 'appliance', label: 'Appliance' },
  { value: 'yard', label: 'Yard Waste' },
  { value: 'general', label: 'General' }
];

const DISPOSAL_METHODS = [
  { value: 'recycled', label: 'Recycled' },
  { value: 'donated', label: 'Donated' },
  { value: 'reused', label: 'Reused' },
  { value: 'landfill', label: 'Landfill' },
  { value: 'hazardous', label: 'Hazardous Waste' },
  { value: 'compost', label: 'Compost' }
];

export function AIReviewInterface({
  aiAnalysis,
  jobId,
  onConfirm,
  onCancel,
  isSubmitting = false
}) {
  const [items, setItems] = useState(aiAnalysis?.ai_analysis?.items || []);
  const [actualWeight, setActualWeight] = useState('');
  const [attestation, setAttestation] = useState(false);
  const [notes, setNotes] = useState('');
  const [showAddItem, setShowAddItem] = useState(false);
  const [newItem, setNewItem] = useState({
    name: '',
    category: 'general',
    weight_lbs: '',
    disposal_method: 'recycled',
    recyclable: true
  });
  const [errors, setErrors] = useState({});

  const confidence = aiAnalysis?.confidence || { score: 0, level: 'low' };
  const style = CONFIDENCE_STYLES[confidence.level] || CONFIDENCE_STYLES.low;

  // Calculate estimated total from items
  const estimatedTotal = items.reduce((sum, item) => sum + (parseFloat(item.weight_lbs) || 0), 0);

  // Validate form
  const validateForm = () => {
    const newErrors = {};

    if (!actualWeight || parseFloat(actualWeight) <= 0) {
      newErrors.actualWeight = 'Actual weight is required';
    }

    if (!attestation) {
      newErrors.attestation = 'You must confirm the attestation';
    }

    if (items.length === 0) {
      newErrors.items = 'At least one item is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle item weight change
  const handleItemWeightChange = (index, newWeight) => {
    const updatedItems = [...items];
    updatedItems[index] = {
      ...updatedItems[index],
      weight_lbs: parseFloat(newWeight) || 0
    };
    setItems(updatedItems);
  };

  // Handle item removal
  const handleRemoveItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  // Handle adding new item
  const handleAddItem = () => {
    if (!newItem.name || !newItem.weight_lbs) return;

    setItems([...items, {
      ...newItem,
      weight_lbs: parseFloat(newItem.weight_lbs),
      added_manually: true
    }]);

    setNewItem({
      name: '',
      category: 'general',
      weight_lbs: '',
      disposal_method: 'recycled',
      recyclable: true
    });
    setShowAddItem(false);
  };

  // Handle form submission
  const handleSubmit = async () => {
    if (!validateForm()) return;

    await onConfirm({
      jobId,
      verifiedItems: items,
      actualWeight: parseFloat(actualWeight),
      attestation: true,
      notes
    });
  };

  return (
    <div className="max-w-4xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Review AI Analysis</h2>
        <p className="text-gray-600 mt-1">
          Job #{aiAnalysis?.job_number || jobId}
        </p>
      </div>

      {/* Confidence Banner */}
      <ConfidenceBanner confidence={confidence} style={style} />

      {/* Instructions */}
      {aiAnalysis?.instructions && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
          <h3 className="font-semibold text-blue-800">
            {aiAnalysis.instructions.title}
          </h3>
          <p className="text-sm text-blue-700 mt-1">
            {aiAnalysis.instructions.message}
          </p>
          <ul className="mt-2 text-sm text-blue-700">
            {aiAnalysis.instructions.requiredActions?.map((action, idx) => (
              <li key={idx} className="flex items-center mt-1">
                <span className="mr-2">*</span>
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Confidence Factors */}
      {confidence.factors?.length > 0 && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="font-medium text-gray-700 mb-2">Analysis Notes:</h4>
          <ul className="space-y-1">
            {confidence.factors.map((factor, idx) => (
              <li key={idx} className="flex items-start text-sm text-gray-600">
                <span className="text-yellow-500 mr-2">!</span>
                {factor}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Items List */}
      <div className="bg-white border rounded-lg p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-900">Detected Items</h3>
          <span className="text-sm text-gray-500">
            {items.length} items - Est. {estimatedTotal.toFixed(1)} lbs
          </span>
        </div>

        {errors.items && (
          <p className="text-red-600 text-sm mb-2">{errors.items}</p>
        )}

        <div className="space-y-3">
          {items.map((item, idx) => (
            <ItemRow
              key={idx}
              item={item}
              onWeightChange={(weight) => handleItemWeightChange(idx, weight)}
              onRemove={() => handleRemoveItem(idx)}
            />
          ))}
        </div>

        {/* Add Item Button */}
        {!showAddItem ? (
          <button
            onClick={() => setShowAddItem(true)}
            className="mt-4 text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            + Add Item AI Missed
          </button>
        ) : (
          <AddItemForm
            newItem={newItem}
            setNewItem={setNewItem}
            onAdd={handleAddItem}
            onCancel={() => setShowAddItem(false)}
          />
        )}
      </div>

      {/* Weight Override - REQUIRED */}
      <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-6 mb-6">
        <h3 className="font-semibold text-gray-900 mb-2">
          Actual Total Weight (Required)
        </h3>
        <p className="text-sm text-gray-700 mb-3">
          AI Estimated: <strong>{estimatedTotal.toFixed(1)} lbs</strong>
        </p>
        <input
          type="number"
          value={actualWeight}
          onChange={(e) => setActualWeight(e.target.value)}
          placeholder="Enter weight from scale or weight ticket"
          className={`w-full p-3 border-2 rounded-lg text-lg ${
            errors.actualWeight ? 'border-red-500' : 'border-yellow-400'
          }`}
          required
        />
        {errors.actualWeight && (
          <p className="text-red-600 text-sm mt-1">{errors.actualWeight}</p>
        )}
        <p className="text-xs text-gray-600 mt-2">
          Use weight from: scale reading, weight ticket, or disposal receipt
        </p>

        {/* Weight Discrepancy Warning */}
        {actualWeight && Math.abs(parseFloat(actualWeight) - estimatedTotal) > estimatedTotal * 0.2 && (
          <div className="mt-3 p-3 bg-orange-100 border border-orange-300 rounded">
            <p className="text-sm text-orange-800">
              <strong>Note:</strong> Actual weight differs significantly from AI estimate
              ({Math.abs(parseFloat(actualWeight) - estimatedTotal).toFixed(1)} lbs difference).
              This is normal - AI estimates can vary.
            </p>
          </div>
        )}
      </div>

      {/* Optional Notes */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Additional Notes (Optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Any corrections or notes about this analysis..."
          className="w-full p-3 border rounded-lg"
          rows={2}
        />
      </div>

      {/* Legal Attestation - REQUIRED */}
      <div className={`p-6 rounded-lg mb-6 ${
        errors.attestation ? 'bg-red-50 border-2 border-red-500' : 'bg-gray-50 border'
      }`}>
        <label className="flex items-start cursor-pointer">
          <input
            type="checkbox"
            checked={attestation}
            onChange={(e) => setAttestation(e.target.checked)}
            className="mt-1 mr-3 h-5 w-5"
            required
          />
          <span className="text-sm">
            <strong>I certify that:</strong> This data is accurate to the best of my knowledge.
            I have verified weights with documentation (scale tickets, receipts, etc.).
            I understand ProofGreen provides data tracking only and does not provide legal or
            regulatory compliance advice.
          </span>
        </label>
        {errors.attestation && (
          <p className="text-red-600 text-sm mt-2">{errors.attestation}</p>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button
          onClick={onCancel}
          disabled={isSubmitting}
          className="flex-1 py-4 px-6 border border-gray-300 rounded-lg font-medium
                     text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!attestation || !actualWeight || isSubmitting}
          className="flex-1 py-4 px-6 bg-green-600 text-white rounded-lg font-bold text-lg
                     disabled:bg-gray-300 disabled:cursor-not-allowed hover:bg-green-700"
        >
          {isSubmitting ? 'Submitting...' : 'Confirm & Generate Report'}
        </button>
      </div>
    </div>
  );
}

// Confidence Banner Component
function ConfidenceBanner({ confidence, style }) {
  return (
    <div className={`${style.bg} border-l-4 ${style.border} p-4 mb-6`}>
      <div className="flex items-start">
        <span className={`text-2xl mr-3 ${style.iconColor}`}>
          {confidence.level === 'high' ? 'check' :
           confidence.level === 'medium' ? 'warning' : 'x'}
        </span>
        <div className="flex-1">
          <div className="flex justify-between items-center">
            <p className={`font-semibold ${style.text}`}>
              AI Confidence: {confidence.score}%
            </p>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${style.bg} ${style.text}`}>
              {confidence.level.toUpperCase()}
            </span>
          </div>
          <p className="text-sm mt-1 text-gray-700">
            {confidence.needsReview ?
              'Please review carefully and verify all items and weights.' :
              'Analysis looks good. Please confirm accuracy before submitting.'}
          </p>
        </div>
      </div>
    </div>
  );
}

// Item Row Component
function ItemRow({ item, onWeightChange, onRemove }) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
      <div className="flex-1">
        <p className="font-medium text-gray-900">{item.name}</p>
        <div className="flex gap-2 text-sm text-gray-600">
          <span className="px-2 py-0.5 bg-gray-200 rounded">{item.category}</span>
          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
            {item.disposal_method || 'recycled'}
          </span>
          {item.added_manually && (
            <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded">
              Manually Added
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="number"
          value={item.weight_lbs}
          onChange={(e) => onWeightChange(e.target.value)}
          className="w-24 p-2 border rounded text-right"
          min="0"
          step="0.1"
        />
        <span className="text-gray-600 text-sm">lbs</span>
        <button
          onClick={onRemove}
          className="text-red-600 hover:text-red-800 p-1"
          title="Remove item"
        >
          X
        </button>
      </div>
    </div>
  );
}

// Add Item Form Component
function AddItemForm({ newItem, setNewItem, onAdd, onCancel }) {
  return (
    <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
      <h4 className="font-medium text-gray-900 mb-3">Add Item</h4>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <input
          type="text"
          placeholder="Item name"
          value={newItem.name}
          onChange={(e) => setNewItem({ ...newItem, name: e.target.value })}
          className="p-2 border rounded"
        />
        <select
          value={newItem.category}
          onChange={(e) => setNewItem({ ...newItem, category: e.target.value })}
          className="p-2 border rounded"
        >
          {CATEGORIES.map(cat => (
            <option key={cat.value} value={cat.value}>{cat.label}</option>
          ))}
        </select>
        <input
          type="number"
          placeholder="Weight (lbs)"
          value={newItem.weight_lbs}
          onChange={(e) => setNewItem({ ...newItem, weight_lbs: e.target.value })}
          className="p-2 border rounded"
          min="0"
          step="0.1"
        />
        <select
          value={newItem.disposal_method}
          onChange={(e) => setNewItem({ ...newItem, disposal_method: e.target.value })}
          className="p-2 border rounded"
        >
          {DISPOSAL_METHODS.map(method => (
            <option key={method.value} value={method.value}>{method.label}</option>
          ))}
        </select>
      </div>
      <div className="flex gap-2">
        <button
          onClick={onAdd}
          disabled={!newItem.name || !newItem.weight_lbs}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700
                     disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          Add Item
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

AIReviewInterface.propTypes = {
  aiAnalysis: PropTypes.shape({
    job_number: PropTypes.string,
    ai_analysis: PropTypes.shape({
      items: PropTypes.array,
      scene_description: PropTypes.string,
      total_estimated_weight: PropTypes.number
    }),
    confidence: PropTypes.shape({
      score: PropTypes.number,
      level: PropTypes.string,
      factors: PropTypes.array,
      needsReview: PropTypes.bool
    }),
    instructions: PropTypes.shape({
      title: PropTypes.string,
      message: PropTypes.string,
      requiredActions: PropTypes.array
    })
  }).isRequired,
  jobId: PropTypes.string.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  isSubmitting: PropTypes.bool
};

export default AIReviewInterface;
