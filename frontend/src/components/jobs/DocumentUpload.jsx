import React, { useState, useRef } from 'react';
import { api } from '../../utils/api';

/**
 * Document Upload Component
 * Upload documents with OCR processing
 */
const DocumentUpload = ({ accept, multiple, documentType, companyId, jobId, onUpload }) => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [error, setError] = useState(null);
  const [selectedDocType, setSelectedDocType] = useState(documentType || '');
  const fileInputRef = useRef(null);

  const documentTypes = [
    { value: 'invoice', label: 'Invoice/Receipt' },
    { value: 'refrigerant_manifest', label: 'Refrigerant Manifest' },
    { value: 'disposal_certificate', label: 'Disposal Certificate' },
    { value: 'epa_certification', label: 'EPA Certification' },
    { value: 'permit', label: 'Permit' },
    { value: 'safety_data_sheet', label: 'Safety Data Sheet (SDS)' },
    { value: 'energy_guide', label: 'EnergyGuide Label' },
    { value: 'recycling_certificate', label: 'Recycling Certificate' },
    { value: 'other', label: 'Other Document' }
  ];

  // Handle file selection
  const handleFileSelect = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
    setError(null);
  };

  // Handle drag and drop
  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles(droppedFiles);
    setError(null);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  // Upload file
  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select a file to upload');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const uploadResults = [];

      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('documentType', selectedDocType || 'other');
        if (companyId) formData.append('companyId', companyId);
        if (jobId) formData.append('jobId', jobId);

        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:3001'}/api/data/documents/upload`, {
          method: 'POST',
          body: formData
        });

        const result = await response.json();

        if (result.success) {
          uploadResults.push({
            file: file.name,
            document: result.document,
            extractedData: result.extractedData
          });
        } else {
          throw new Error(result.error || 'Upload failed');
        }
      }

      setUploadedDocs(prev => [...prev, ...uploadResults]);
      setFiles([]);

      if (onUpload) {
        onUpload(uploadResults);
      }

    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  // Remove uploaded document
  const handleRemoveUploaded = (index) => {
    setUploadedDocs(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      {/* Document type selector */}
      {!documentType && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Document Type
          </label>
          <select
            value={selectedDocType}
            onChange={(e) => setSelectedDocType(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            <option value="">Auto-detect</option>
            {documentTypes.map(type => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          files.length > 0 ? 'border-green-400 bg-green-50' : 'border-gray-300 hover:border-green-400'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={accept || 'image/*,application/pdf'}
          multiple={multiple}
          onChange={handleFileSelect}
          className="hidden"
        />

        {files.length > 0 ? (
          <div>
            <svg className="mx-auto h-10 w-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="mt-2 text-sm text-green-700">
              {files.length} file{files.length > 1 ? 's' : ''} selected
            </p>
            <ul className="mt-2 text-xs text-gray-500">
              {files.map((file, i) => (
                <li key={i}>{file.name} ({(file.size / 1024).toFixed(1)} KB)</li>
              ))}
            </ul>
          </div>
        ) : (
          <div>
            <svg className="mx-auto h-10 w-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="mt-2 text-sm text-gray-600">
              <span className="text-green-600 font-medium">Click to upload</span> or drag and drop
            </p>
            <p className="text-xs text-gray-500 mt-1">
              PNG, JPG, PDF up to 10MB
            </p>
          </div>
        )}
      </div>

      {/* Upload button */}
      {files.length > 0 && (
        <button
          type="button"
          onClick={handleUpload}
          disabled={uploading}
          className="w-full py-2 px-4 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 font-medium flex items-center justify-center gap-2"
        >
          {uploading ? (
            <>
              <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full"></div>
              Processing with OCR...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              Upload & Extract Data
            </>
          )}
        </button>
      )}

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Uploaded documents with extracted data */}
      {uploadedDocs.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-gray-900">Processed Documents</h4>

          {uploadedDocs.map((doc, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <p className="font-medium text-gray-900">{doc.file}</p>
                  <p className="text-xs text-gray-500">
                    Type: {doc.extractedData?.document_type || 'Unknown'}
                    {doc.extractedData?.confidence && (
                      <span className="ml-2">
                        Confidence: {(doc.extractedData.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveUploaded(index)}
                  className="text-gray-400 hover:text-red-500"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Extracted data display */}
              {doc.extractedData?.extracted_data && Object.keys(doc.extractedData.extracted_data).length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-gray-500 mb-2">Extracted Data</p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(doc.extractedData.extracted_data).map(([key, value]) => (
                      value && (
                        <div key={key}>
                          <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}: </span>
                          <span className="text-gray-900">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}

              {/* ESG relevant data */}
              {doc.extractedData?.esg_relevant_data && Object.keys(doc.extractedData.esg_relevant_data).length > 0 && (
                <div className="mt-3 bg-green-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-green-700 mb-2">ESG-Relevant Data</p>
                  <div className="text-sm text-green-800">
                    {Object.entries(doc.extractedData.esg_relevant_data).map(([key, value]) => (
                      value && (
                        <div key={key}>
                          <span className="capitalize">{key.replace(/_/g, ' ')}: </span>
                          <span className="font-medium">{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {doc.extractedData?.warnings && doc.extractedData.warnings.length > 0 && (
                <div className="mt-3 bg-yellow-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-yellow-700 mb-1">Notes</p>
                  <ul className="text-sm text-yellow-800 list-disc list-inside">
                    {doc.extractedData.warnings.map((warning, i) => (
                      <li key={i}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DocumentUpload;
