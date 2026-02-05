import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CloudArrowUpIcon,
  DocumentIcon,
  CheckCircleIcon,
  XCircleIcon,
  TrashIcon,
  SparklesIcon,
  EyeIcon
} from '@heroicons/react/24/outline';
import api from '../../utils/api';
import toast from 'react-hot-toast';

export default function DocumentUpload({ jobId, onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [selectedType, setSelectedType] = useState('');
  const [expiryDate, setExpiryDate] = useState('');

  const documentTypes = [
    { value: 'weight_ticket', label: 'Weight Ticket' },
    { value: 'donation_receipt', label: 'Donation Receipt' },
    { value: 'epa_certification', label: 'EPA Certification' },
    { value: 'recycling_receipt', label: 'Recycling Receipt' },
    { value: 'safety_data_sheet', label: 'Safety Data Sheet' },
    { value: 'energy_star_cert', label: 'Energy Star Certificate' },
    { value: 'insurance_cert', label: 'Insurance Certificate' },
    { value: 'license', label: 'License' },
    { value: 'osha_cert', label: 'OSHA Certification' },
    { value: 'refrigerant_log', label: 'Refrigerant Log' },
    { value: 'disposal_manifest', label: 'Disposal Manifest' },
    { value: 'permit', label: 'Permit' },
    { value: 'inspection', label: 'Inspection Report' },
    { value: 'other', label: 'Other' }
  ];

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;

    setUploading(true);

    for (const file of acceptedFiles) {
      try {
        const formData = new FormData();
        formData.append('document', file);
        if (jobId) formData.append('jobId', jobId);
        if (selectedType) formData.append('documentType', selectedType);
        if (expiryDate) formData.append('expiresAt', expiryDate);

        const response = await api.post('/documents/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });

        const doc = response.data.document;
        setUploadedDocs(prev => [...prev, {
          ...doc,
          originalFile: file,
          aiMessage: response.data.message
        }]);

        toast.success(response.data.message || 'Document uploaded successfully');
      } catch (error) {
        toast.error(`Failed to upload ${file.name}`);
        console.error(error);
      }
    }

    setUploading(false);
    if (onUploadComplete) {
      onUploadComplete(uploadedDocs);
    }
  }, [jobId, selectedType, expiryDate, onUploadComplete, uploadedDocs]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
      'application/pdf': ['.pdf']
    },
    maxSize: 25 * 1024 * 1024 // 25MB
  });

  const removeDocument = async (docId) => {
    try {
      await api.delete(`/documents/${docId}`);
      setUploadedDocs(prev => prev.filter(d => d.id !== docId));
      toast.success('Document removed');
    } catch (error) {
      toast.error('Failed to remove document');
    }
  };

  const verifyDocument = async (docId) => {
    try {
      await api.put(`/documents/${docId}/verify`);
      setUploadedDocs(prev => prev.map(d =>
        d.id === docId ? { ...d, verified: true } : d
      ));
      toast.success('Document verified');
    } catch (error) {
      toast.error('Failed to verify document');
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Options */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Document Type (Optional)
          </label>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500"
          >
            <option value="">Auto-detect with AI</option>
            {documentTypes.map(type => (
              <option key={type.value} value={type.value}>{type.label}</option>
            ))}
          </select>
          <p className="text-xs text-gray-500 mt-1">Leave blank for AI-powered categorization</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Expiry Date (Optional)
          </label>
          <input
            type="date"
            value={expiryDate}
            onChange={(e) => setExpiryDate(e.target.value)}
            className="block w-full rounded-lg border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500"
          />
          <p className="text-xs text-gray-500 mt-1">Set expiry for certifications & licenses</p>
        </div>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-green-500 bg-green-50'
            : 'border-gray-300 hover:border-green-400 hover:bg-gray-50'
        }`}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mb-4"></div>
            <p className="text-gray-600">Uploading and analyzing documents...</p>
            <p className="text-sm text-gray-500 mt-1">AI is categorizing your documents</p>
          </div>
        ) : (
          <>
            <CloudArrowUpIcon className={`h-12 w-12 mx-auto mb-4 ${isDragActive ? 'text-green-600' : 'text-gray-400'}`} />
            <p className="text-lg font-medium text-gray-700">
              {isDragActive ? 'Drop files here' : 'Drag & drop documents here'}
            </p>
            <p className="text-sm text-gray-500 mt-1">or click to browse</p>
            <div className="mt-4 flex items-center justify-center space-x-4 text-xs text-gray-400">
              <span>JPG, PNG, WebP, PDF</span>
              <span>Max 25MB</span>
            </div>
            <div className="mt-4 flex items-center justify-center">
              <SparklesIcon className="h-4 w-4 text-purple-500 mr-1" />
              <span className="text-sm text-purple-600">AI-powered categorization & data extraction</span>
            </div>
          </>
        )}
      </div>

      {/* Uploaded Documents */}
      <AnimatePresence>
        {uploadedDocs.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <h3 className="text-lg font-semibold text-gray-900">Uploaded Documents</h3>

            {uploadedDocs.map((doc, index) => (
              <motion.div
                key={doc.id || index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="bg-white rounded-lg border shadow-sm p-4"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <DocumentIcon className="h-6 w-6 text-gray-600" />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{doc.fileName}</p>
                      <p className="text-sm text-gray-500">
                        {doc.documentType?.replace(/_/g, ' ')}
                      </p>

                      {doc.aiCategorized && (
                        <div className="mt-2 flex items-center space-x-2">
                          <SparklesIcon className="h-4 w-4 text-purple-500" />
                          <span className="text-xs text-purple-600">
                            AI categorized with {Math.round((doc.aiConfidence || 0) * 100)}% confidence
                          </span>
                        </div>
                      )}

                      {doc.extractedData && Object.keys(doc.extractedData).length > 0 && (
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
                          <p className="font-medium text-gray-700 mb-1">Extracted Data:</p>
                          {Object.entries(doc.extractedData).slice(0, 3).map(([key, value]) => (
                            <p key={key} className="text-gray-600">
                              <span className="font-medium">{key}:</span> {String(value)}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {doc.verified ? (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-green-100 text-green-800">
                        <CheckCircleIcon className="h-4 w-4 mr-1" />
                        Verified
                      </span>
                    ) : (
                      <button
                        onClick={() => verifyDocument(doc.id)}
                        className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
                      >
                        <CheckCircleIcon className="h-4 w-4 mr-1" />
                        Verify
                      </button>
                    )}

                    <button
                      onClick={() => window.open(`/api/documents/${doc.id}`, '_blank')}
                      className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                      title="View document"
                    >
                      <EyeIcon className="h-5 w-5" />
                    </button>

                    <button
                      onClick={() => removeDocument(doc.id)}
                      className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                      title="Remove document"
                    >
                      <TrashIcon className="h-5 w-5" />
                    </button>
                  </div>
                </div>

                {doc.aiMessage && (
                  <div className="mt-3 p-2 bg-green-50 rounded-lg">
                    <p className="text-sm text-green-700">{doc.aiMessage}</p>
                  </div>
                )}
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
