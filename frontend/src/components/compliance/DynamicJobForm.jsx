import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DocumentTextIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import api from '../../utils/api';
import toast from 'react-hot-toast';

export default function DynamicJobForm({ jobId, verticalSlug, onSubmit, initialData = {} }) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [fields, setFields] = useState([]);
  const [sections, setSections] = useState({});
  const [formData, setFormData] = useState(initialData);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (verticalSlug) {
      fetchFormFields();
    }
  }, [verticalSlug]);

  const fetchFormFields = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/compliance/form-fields/${verticalSlug}`);
      setFields(response.data.fields);
      setSections(response.data.sections);

      // Initialize form data with defaults
      const defaults = {};
      response.data.fields.forEach(field => {
        if (field.default !== undefined) {
          defaults[field.name] = field.default;
        }
      });
      setFormData(prev => ({ ...defaults, ...prev }));
    } catch (error) {
      toast.error('Failed to load form fields');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (fieldName, value) => {
    setFormData(prev => ({ ...prev, [fieldName]: value }));
    // Clear error when field is modified
    if (errors[fieldName]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldName];
        return newErrors;
      });
    }
  };

  const validateForm = () => {
    const newErrors = {};
    fields.forEach(field => {
      if (field.required && (formData[field.name] === undefined || formData[field.name] === '')) {
        newErrors[field.name] = `${field.label} is required`;
      }
      if (field.min !== undefined && formData[field.name] < field.min) {
        newErrors[field.name] = `${field.label} must be at least ${field.min}`;
      }
      if (field.max !== undefined && formData[field.name] > field.max) {
        newErrors[field.name] = `${field.label} must be at most ${field.max}`;
      }
    });
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) {
      toast.error('Please fix the errors before submitting');
      return;
    }

    try {
      setSubmitting(true);
      const response = await api.post('/compliance/esg-data', {
        jobId,
        verticalSlug,
        formData
      });

      toast.success('ESG data saved successfully');
      if (onSubmit) {
        onSubmit(response.data);
      }
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to save ESG data');
      if (error.response?.data?.validationErrors) {
        setErrors(error.response.data.validationErrors);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const renderField = (field) => {
    const hasError = errors[field.name];
    const baseInputClass = `block w-full rounded-lg border ${hasError ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : 'border-gray-300 focus:border-green-500 focus:ring-green-500'} shadow-sm`;

    switch (field.type) {
      case 'number':
        return (
          <input
            type="number"
            id={field.name}
            value={formData[field.name] ?? ''}
            onChange={(e) => handleChange(field.name, parseFloat(e.target.value) || '')}
            min={field.min}
            max={field.max}
            step={field.step || 1}
            className={baseInputClass}
            placeholder={field.placeholder}
          />
        );

      case 'select':
        return (
          <select
            id={field.name}
            value={formData[field.name] ?? ''}
            onChange={(e) => handleChange(field.name, e.target.value)}
            className={baseInputClass}
          >
            <option value="">Select {field.label}</option>
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        );

      case 'checkbox':
        return (
          <div className="flex items-center">
            <input
              type="checkbox"
              id={field.name}
              checked={formData[field.name] ?? false}
              onChange={(e) => handleChange(field.name, e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
            />
            <label htmlFor={field.name} className="ml-2 text-sm text-gray-600">
              {field.checkboxLabel || 'Yes'}
            </label>
          </div>
        );

      case 'textarea':
        return (
          <textarea
            id={field.name}
            value={formData[field.name] ?? ''}
            onChange={(e) => handleChange(field.name, e.target.value)}
            rows={3}
            className={baseInputClass}
            placeholder={field.placeholder}
          />
        );

      case 'date':
        return (
          <input
            type="date"
            id={field.name}
            value={formData[field.name] ?? ''}
            onChange={(e) => handleChange(field.name, e.target.value)}
            className={baseInputClass}
          />
        );

      default:
        return (
          <input
            type="text"
            id={field.name}
            value={formData[field.name] ?? ''}
            onChange={(e) => handleChange(field.name, e.target.value)}
            className={baseInputClass}
            placeholder={field.placeholder}
          />
        );
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    );
  }

  if (fields.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <DocumentTextIcon className="h-12 w-12 mx-auto mb-4 text-gray-400" />
        <p>No ESG form fields configured for this vertical.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <AnimatePresence>
        {Object.entries(sections).map(([sectionName, sectionFields], sectionIndex) => (
          <motion.div
            key={sectionName}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: sectionIndex * 0.1 }}
            className="bg-white rounded-xl shadow-lg p-6"
          >
            <h3 className="text-lg font-semibold text-gray-900 mb-4 capitalize flex items-center">
              <DocumentTextIcon className="h-5 w-5 mr-2 text-green-600" />
              {sectionName.replace(/_/g, ' ')}
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {sectionFields.map((field) => (
                <div key={field.name} className={field.type === 'textarea' ? 'md:col-span-2' : ''}>
                  <label htmlFor={field.name} className="block text-sm font-medium text-gray-700 mb-1">
                    {field.label}
                    {field.required && <span className="text-red-500 ml-1">*</span>}
                  </label>

                  {field.helpText && (
                    <p className="text-xs text-gray-500 mb-2 flex items-center">
                      <InformationCircleIcon className="h-4 w-4 mr-1" />
                      {field.helpText}
                    </p>
                  )}

                  {renderField(field)}

                  {field.unit && (
                    <p className="text-xs text-gray-500 mt-1">{field.unit}</p>
                  )}

                  {errors[field.name] && (
                    <p className="text-sm text-red-600 mt-1 flex items-center">
                      <ExclamationCircleIcon className="h-4 w-4 mr-1" />
                      {errors[field.name]}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Summary Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: Object.keys(sections).length * 0.1 }}
        className="bg-green-50 rounded-xl p-6"
      >
        <h3 className="text-lg font-semibold text-green-900 mb-2 flex items-center">
          <CheckCircleIcon className="h-5 w-5 mr-2" />
          Ready to Submit
        </h3>
        <p className="text-sm text-green-700 mb-4">
          Your ESG data will be processed and your compliance score will be updated automatically.
        </p>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-green-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Saving ESG Data...
            </span>
          ) : (
            'Save ESG Data & Calculate Score'
          )}
        </button>
      </motion.div>
    </form>
  );
}
