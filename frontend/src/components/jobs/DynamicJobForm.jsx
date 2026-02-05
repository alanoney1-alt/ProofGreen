import React, { useState, useEffect } from 'react';
import { api } from '../../utils/api';
import EquipmentLookup from './EquipmentLookup';
import ChemicalLookup from './ChemicalLookup';
import MaterialSelector from './MaterialSelector';
import DocumentUpload from './DocumentUpload';
import TripCalculator from './TripCalculator';

/**
 * Dynamic Job Form Component
 * Renders form fields based on vertical-specific configuration
 */
const DynamicJobForm = ({ verticalSlug, jobId, initialData, onSubmit, onCancel }) => {
  const [formConfig, setFormConfig] = useState(null);
  const [formData, setFormData] = useState(initialData || {});
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [activeSection, setActiveSection] = useState(0);

  // Load form configuration for vertical
  useEffect(() => {
    const loadFormConfig = async () => {
      try {
        setLoading(true);
        const response = await api.get(`/data/forms/${verticalSlug}`);
        if (response.success) {
          setFormConfig(response.formConfig);
        }
      } catch (error) {
        console.error('Failed to load form config:', error);
      } finally {
        setLoading(false);
      }
    };

    if (verticalSlug) {
      loadFormConfig();
    }
  }, [verticalSlug]);

  // Update form data
  const handleFieldChange = (fieldName, value) => {
    setFormData(prev => ({
      ...prev,
      [fieldName]: value
    }));

    // Clear error for this field
    if (errors[fieldName]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldName];
        return newErrors;
      });
    }
  };

  // Check if section should be shown based on conditions
  const shouldShowSection = (section) => {
    if (!section.showIf) return true;

    // Parse simple conditions like "field === value"
    const condition = section.showIf;
    const match = condition.match(/(\w+)\s*(===|!==|includes)\s*(.+)/);

    if (!match) return true;

    const [, fieldName, operator, expectedValue] = match;
    const actualValue = formData[fieldName];

    switch (operator) {
      case '===':
        return String(actualValue) === expectedValue.trim().replace(/['"]/g, '');
      case '!==':
        return String(actualValue) !== expectedValue.trim().replace(/['"]/g, '');
      case 'includes':
        return Array.isArray(actualValue) && actualValue.includes(expectedValue.trim().replace(/['"]/g, ''));
      default:
        return true;
    }
  };

  // Check if field should be shown
  const shouldShowField = (field) => {
    if (!field.showIf) return true;

    const condition = field.showIf;
    const match = condition.match(/(\w+)\s*(===|!==|>|<|>=|<=)\s*(.+)/);

    if (!match) return true;

    const [, fieldName, operator, expectedValue] = match;
    const actualValue = formData[fieldName];

    switch (operator) {
      case '===':
        return String(actualValue) === expectedValue.trim().replace(/['"]/g, '');
      case '!==':
        return String(actualValue) !== expectedValue.trim().replace(/['"]/g, '');
      case '>':
        return parseFloat(actualValue) > parseFloat(expectedValue);
      case '<':
        return parseFloat(actualValue) < parseFloat(expectedValue);
      case '>=':
        return parseFloat(actualValue) >= parseFloat(expectedValue);
      case '<=':
        return parseFloat(actualValue) <= parseFloat(expectedValue);
      default:
        return true;
    }
  };

  // Render a single field based on type
  const renderField = (field) => {
    if (!shouldShowField(field)) return null;

    const value = formData[field.name] || '';
    const error = errors[field.name];

    const baseInputClass = `w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 ${
      error ? 'border-red-500' : 'border-gray-300'
    }`;

    switch (field.type) {
      case 'text':
      case 'number':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <input
              type={field.type}
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder}
              min={field.min}
              max={field.max}
              step={field.step}
              className={baseInputClass}
            />
            {field.helperText && (
              <p className="text-xs text-gray-500 mt-1">{field.helperText}</p>
            )}
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
          </div>
        );

      case 'textarea':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <textarea
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              rows={4}
              className={baseInputClass}
            />
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
          </div>
        );

      case 'select':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <select
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              className={baseInputClass}
            >
              <option value="">Select...</option>
              {field.options?.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
          </div>
        );

      case 'multiselect':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <div className="border border-gray-300 rounded-lg p-2 max-h-40 overflow-y-auto">
              {field.options?.map((option) => (
                <label key={option} className="flex items-center space-x-2 py-1">
                  <input
                    type="checkbox"
                    checked={(value || []).includes(option)}
                    onChange={(e) => {
                      const current = value || [];
                      const updated = e.target.checked
                        ? [...current, option]
                        : current.filter((v) => v !== option);
                      handleFieldChange(field.name, updated);
                    }}
                    className="rounded text-green-600"
                  />
                  <span className="text-sm">{option}</span>
                </label>
              ))}
            </div>
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
          </div>
        );

      case 'boolean':
        return (
          <div key={field.name} className="mb-4">
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={value === true}
                onChange={(e) => handleFieldChange(field.name, e.target.checked)}
                className="w-5 h-5 rounded text-green-600"
              />
              <span className="text-sm font-medium text-gray-700">{field.label}</span>
            </label>
            {field.helperText && (
              <p className="text-xs text-gray-500 mt-1 ml-8">{field.helperText}</p>
            )}
          </div>
        );

      case 'date':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <input
              type="date"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              className={baseInputClass}
            />
            {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
          </div>
        );

      case 'equipment_lookup':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <EquipmentLookup
              category={field.category}
              value={value}
              onChange={(equipment) => handleFieldChange(field.name, equipment)}
            />
          </div>
        );

      case 'refrigerant_lookup':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <RefrigerantSelect
              value={value}
              onChange={(val) => handleFieldChange(field.name, val)}
            />
          </div>
        );

      case 'chemical_lookup':
      case 'chemical_list':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <ChemicalLookup
              value={value}
              onChange={(chemicals) => handleFieldChange(field.name, chemicals)}
              multiple={field.type === 'chemical_list'}
            />
          </div>
        );

      case 'material_list':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <MaterialSelector
              categories={field.categories}
              value={value}
              onChange={(materials) => handleFieldChange(field.name, materials)}
            />
          </div>
        );

      case 'file':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <DocumentUpload
              accept={field.accept}
              multiple={field.multiple}
              onUpload={(docs) => handleFieldChange(field.name, docs)}
            />
          </div>
        );

      case 'address':
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            <input
              type="text"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder="Enter full address"
              className={baseInputClass}
            />
          </div>
        );

      default:
        return (
          <div key={field.name} className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <input
              type="text"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              className={baseInputClass}
            />
          </div>
        );
    }
  };

  // Validate form
  const validateForm = () => {
    const newErrors = {};
    const sections = formConfig?.form_config?.sections || [];

    sections.forEach((section) => {
      if (!shouldShowSection(section)) return;

      section.fields?.forEach((field) => {
        if (!shouldShowField(field)) return;

        if (field.required && !formData[field.name]) {
          newErrors[field.name] = `${field.label} is required`;
        }
      });
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    onSubmit(formData);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
        <span className="ml-3 text-gray-600">Loading form...</span>
      </div>
    );
  }

  if (!formConfig) {
    return (
      <div className="p-8 text-center text-gray-500">
        <p>No form configuration available for this service type.</p>
        <p className="text-sm mt-2">Please use the basic job form.</p>
      </div>
    );
  }

  const sections = formConfig.form_config?.sections || [];
  const visibleSections = sections.filter(shouldShowSection);

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Section tabs */}
      <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-4">
        {visibleSections.map((section, index) => (
          <button
            key={section.id}
            type="button"
            onClick={() => setActiveSection(index)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeSection === index
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {section.title}
          </button>
        ))}
      </div>

      {/* Active section content */}
      {visibleSections[activeSection] && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {visibleSections[activeSection].title}
          </h3>
          {visibleSections[activeSection].description && (
            <p className="text-sm text-gray-500 mb-4">
              {visibleSections[activeSection].description}
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {visibleSections[activeSection].fields?.map(renderField)}
          </div>
        </div>
      )}

      {/* Navigation and submit */}
      <div className="flex justify-between items-center pt-4 border-t border-gray-200">
        <div className="flex gap-2">
          {activeSection > 0 && (
            <button
              type="button"
              onClick={() => setActiveSection(activeSection - 1)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Previous
            </button>
          )}
          {activeSection < visibleSections.length - 1 && (
            <button
              type="button"
              onClick={() => setActiveSection(activeSection + 1)}
              className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
            >
              Next Section
            </button>
          )}
        </div>

        <div className="flex gap-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
          >
            Save Job Data
          </button>
        </div>
      </div>
    </form>
  );
};

/**
 * Refrigerant Select Component
 */
const RefrigerantSelect = ({ value, onChange }) => {
  const [refrigerants, setRefrigerants] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadRefrigerants = async () => {
      try {
        const response = await api.get('/data/refrigerants');
        if (response.success) {
          setRefrigerants(response.refrigerants);
        }
      } catch (error) {
        console.error('Failed to load refrigerants:', error);
      } finally {
        setLoading(false);
      }
    };
    loadRefrigerants();
  }, []);

  if (loading) {
    return <div className="animate-pulse h-10 bg-gray-200 rounded"></div>;
  }

  return (
    <select
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
    >
      <option value="">Select refrigerant...</option>
      {refrigerants.map((ref) => (
        <option key={ref.id} value={ref.id}>
          {ref.epa_designation} - {ref.name} (GWP: {ref.gwp_value})
        </option>
      ))}
      <option value="other">Other (specify)</option>
    </select>
  );
};

export default DynamicJobForm;
