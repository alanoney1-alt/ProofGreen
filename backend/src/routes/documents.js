const express = require('express');
const router = express.Router();
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');
const { supabase } = require('../utils/supabase');
const { authenticate, authorize } = require('../middleware/auth');
const { logger } = require('../utils/logger');
const OpenAI = require('openai');

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// Configure multer for document uploads
const storage = multer.memoryStorage();
const upload = multer({
  storage,
  limits: { fileSize: 25 * 1024 * 1024 }, // 25MB limit
  fileFilter: (req, file, cb) => {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (allowedTypes.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Only images and PDFs are allowed'));
    }
  }
});

// Document type mappings for AI categorization
const DOCUMENT_TYPES = {
  weight_ticket: ['weight ticket', 'scale ticket', 'weighbridge', 'weight receipt'],
  donation_receipt: ['donation receipt', 'charitable donation', 'tax receipt', 'charity receipt'],
  epa_certification: ['epa 608', 'epa certification', 'refrigerant certification', 'section 608'],
  recycling_receipt: ['recycling receipt', 'scrap receipt', 'metal recycling'],
  safety_data_sheet: ['safety data sheet', 'sds', 'msds', 'material safety'],
  energy_star_cert: ['energy star', 'energystar'],
  watersense_cert: ['watersense', 'water sense'],
  insurance_cert: ['insurance certificate', 'certificate of insurance', 'coi', 'liability insurance'],
  license: ['license', 'contractor license', 'business license', 'trade license'],
  osha_cert: ['osha', 'safety training', 'osha 10', 'osha 30'],
  refrigerant_log: ['refrigerant log', 'refrigerant recovery', 'r-22', 'r-410a'],
  disposal_manifest: ['disposal manifest', 'hazardous waste manifest', 'epa manifest'],
  cool_roof_cert: ['cool roof', 'energy star roof', 'reflective roof'],
  cims_gb_cert: ['cims', 'cleaning industry', 'cims-gb'],
  pesticide_log: ['pesticide', 'pesticide application', 'pest control log'],
  leed_documentation: ['leed', 'green building', 'leed credit'],
  e_waste_receipt: ['e-waste', 'electronic waste', 'ewaste'],
  solar_interconnection: ['interconnection', 'solar agreement', 'net metering'],
  copper_recycling_receipt: ['copper', 'brass', 'metal scrap'],
  hazmat_manifest: ['hazmat', 'hazardous material', 'asbestos', 'lead paint'],
  permit: ['permit', 'building permit', 'work permit'],
  inspection: ['inspection', 'inspection report', 'final inspection']
};

// POST /api/documents/upload
router.post('/upload', authenticate, upload.single('document'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No document uploaded' });
    }

    const { jobId, documentType, expiresAt } = req.body;

    // Convert file to base64 for storage
    const fileBase64 = req.file.buffer.toString('base64');
    const fileUrl = `data:${req.file.mimetype};base64,${fileBase64}`;

    // AI Categorization if type not specified
    let detectedType = documentType;
    let aiConfidence = null;
    let extractedData = {};

    if (!documentType && req.file.mimetype.startsWith('image/')) {
      try {
        const categorization = await categorizeDocument(fileBase64, req.file.mimetype);
        detectedType = categorization.type;
        aiConfidence = categorization.confidence;
        extractedData = categorization.extractedData || {};
      } catch (aiError) {
        logger.warn('AI categorization failed:', aiError);
        detectedType = 'other';
      }
    }

    // Create document record
    const documentRecord = {
      company_id: req.companyId,
      job_id: jobId || null,
      document_type: detectedType || 'other',
      document_url: fileUrl,
      file_name: req.file.originalname,
      file_size_bytes: req.file.size,
      mime_type: req.file.mimetype,
      extracted_data: extractedData,
      expires_at: expiresAt || null,
      ai_categorized: !documentType && aiConfidence !== null,
      ai_confidence: aiConfidence,
      ai_suggested_type: !documentType ? detectedType : null
    };

    const { data: document, error } = await supabase
      .from('esg_documents')
      .insert(documentRecord)
      .select()
      .single();

    if (error) {
      logger.error('Document insert error:', error);
      return res.status(500).json({ error: 'Failed to save document' });
    }

    // Link to requirement if applicable
    if (jobId && detectedType) {
      await linkDocumentToRequirement(document.id, jobId, detectedType);
    }

    logger.info(`Document uploaded: ${document.id} (${detectedType}) for company ${req.companyId}`);

    res.status(201).json({
      document: {
        id: document.id,
        documentType: document.document_type,
        fileName: document.file_name,
        aiCategorized: document.ai_categorized,
        aiConfidence: document.ai_confidence,
        extractedData: document.extracted_data,
        uploadedAt: document.uploaded_at
      },
      message: document.ai_categorized
        ? `Document categorized as "${detectedType}" with ${Math.round(aiConfidence * 100)}% confidence`
        : 'Document uploaded successfully'
    });
  } catch (error) {
    logger.error('Document upload error:', error);
    res.status(500).json({ error: 'Failed to upload document' });
  }
});

// GET /api/documents/job/:jobId
router.get('/job/:jobId', authenticate, async (req, res) => {
  try {
    const { jobId } = req.params;

    // Verify job belongs to company
    const { data: job } = await supabase
      .from('jobs')
      .select('id')
      .eq('id', jobId)
      .eq('company_id', req.companyId)
      .single();

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    const { data: documents, error } = await supabase
      .from('esg_documents')
      .select('*')
      .eq('job_id', jobId)
      .order('uploaded_at', { ascending: false });

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch documents' });
    }

    // Don't return full base64 data in list
    const sanitized = documents.map(doc => ({
      id: doc.id,
      documentType: doc.document_type,
      fileName: doc.file_name,
      fileSize: doc.file_size_bytes,
      mimeType: doc.mime_type,
      extractedData: doc.extracted_data,
      uploadedAt: doc.uploaded_at,
      expiresAt: doc.expires_at,
      verified: doc.verified,
      verifiedAt: doc.verified_at,
      aiCategorized: doc.ai_categorized,
      aiConfidence: doc.ai_confidence
    }));

    res.json({ documents: sanitized });
  } catch (error) {
    logger.error('Get job documents error:', error);
    res.status(500).json({ error: 'Failed to fetch documents' });
  }
});

// GET /api/documents/company
router.get('/company', authenticate, async (req, res) => {
  try {
    const { type, verified, expiring } = req.query;

    let query = supabase
      .from('esg_documents')
      .select('*')
      .eq('company_id', req.companyId)
      .order('uploaded_at', { ascending: false });

    if (type) {
      query = query.eq('document_type', type);
    }

    if (verified === 'true') {
      query = query.eq('verified', true);
    } else if (verified === 'false') {
      query = query.eq('verified', false);
    }

    // Filter for expiring documents
    if (expiring) {
      const daysAhead = parseInt(expiring) || 30;
      const futureDate = new Date();
      futureDate.setDate(futureDate.getDate() + daysAhead);
      query = query
        .not('expires_at', 'is', null)
        .lte('expires_at', futureDate.toISOString())
        .gte('expires_at', new Date().toISOString());
    }

    const { data: documents, error } = await query;

    if (error) {
      return res.status(500).json({ error: 'Failed to fetch documents' });
    }

    // Don't return full base64 data
    const sanitized = documents.map(doc => ({
      id: doc.id,
      jobId: doc.job_id,
      documentType: doc.document_type,
      fileName: doc.file_name,
      fileSize: doc.file_size_bytes,
      mimeType: doc.mime_type,
      extractedData: doc.extracted_data,
      uploadedAt: doc.uploaded_at,
      expiresAt: doc.expires_at,
      verified: doc.verified,
      verifiedAt: doc.verified_at,
      aiCategorized: doc.ai_categorized,
      aiConfidence: doc.ai_confidence
    }));

    // Group by type for summary
    const byType = sanitized.reduce((acc, doc) => {
      acc[doc.documentType] = (acc[doc.documentType] || 0) + 1;
      return acc;
    }, {});

    res.json({
      documents: sanitized,
      summary: {
        total: sanitized.length,
        verified: sanitized.filter(d => d.verified).length,
        byType
      }
    });
  } catch (error) {
    logger.error('Get company documents error:', error);
    res.status(500).json({ error: 'Failed to fetch documents' });
  }
});

// GET /api/documents/:id
router.get('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    const { data: document, error } = await supabase
      .from('esg_documents')
      .select('*')
      .eq('id', id)
      .eq('company_id', req.companyId)
      .single();

    if (error || !document) {
      return res.status(404).json({ error: 'Document not found' });
    }

    res.json({ document });
  } catch (error) {
    logger.error('Get document error:', error);
    res.status(500).json({ error: 'Failed to fetch document' });
  }
});

// PUT /api/documents/:id/verify
router.put('/:id/verify', authenticate, authorize('owner', 'admin', 'manager'), async (req, res) => {
  try {
    const { id } = req.params;
    const { notes } = req.body;

    const { data: document, error } = await supabase
      .from('esg_documents')
      .update({
        verified: true,
        verified_by: req.user.id,
        verified_at: new Date().toISOString(),
        verification_notes: notes
      })
      .eq('id', id)
      .eq('company_id', req.companyId)
      .select()
      .single();

    if (error || !document) {
      return res.status(404).json({ error: 'Document not found' });
    }

    logger.info(`Document ${id} verified by user ${req.user.id}`);

    res.json({
      document: {
        id: document.id,
        verified: document.verified,
        verifiedAt: document.verified_at,
        verifiedBy: document.verified_by
      },
      message: 'Document verified successfully'
    });
  } catch (error) {
    logger.error('Verify document error:', error);
    res.status(500).json({ error: 'Failed to verify document' });
  }
});

// PUT /api/documents/:id
router.put('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;
    const { documentType, expiresAt, jobId } = req.body;

    const updates = {};
    if (documentType) updates.document_type = documentType;
    if (expiresAt !== undefined) updates.expires_at = expiresAt;
    if (jobId !== undefined) updates.job_id = jobId;

    const { data: document, error } = await supabase
      .from('esg_documents')
      .update(updates)
      .eq('id', id)
      .eq('company_id', req.companyId)
      .select()
      .single();

    if (error || !document) {
      return res.status(404).json({ error: 'Document not found' });
    }

    res.json({ document });
  } catch (error) {
    logger.error('Update document error:', error);
    res.status(500).json({ error: 'Failed to update document' });
  }
});

// DELETE /api/documents/:id
router.delete('/:id', authenticate, async (req, res) => {
  try {
    const { id } = req.params;

    const { error } = await supabase
      .from('esg_documents')
      .delete()
      .eq('id', id)
      .eq('company_id', req.companyId);

    if (error) {
      return res.status(500).json({ error: 'Failed to delete document' });
    }

    res.json({ message: 'Document deleted successfully' });
  } catch (error) {
    logger.error('Delete document error:', error);
    res.status(500).json({ error: 'Failed to delete document' });
  }
});

// GET /api/documents/types
router.get('/meta/types', authenticate, async (req, res) => {
  res.json({
    types: Object.keys(DOCUMENT_TYPES).map(key => ({
      value: key,
      label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      keywords: DOCUMENT_TYPES[key]
    }))
  });
});

// AI Document Categorization
async function categorizeDocument(base64Data, mimeType) {
  try {
    const response = await openai.chat.completions.create({
      model: 'gpt-4o',
      max_tokens: 500,
      messages: [
        {
          role: 'system',
          content: `You are a document classifier for ESG compliance. Analyze the document and:
1. Identify the document type from this list: ${Object.keys(DOCUMENT_TYPES).join(', ')}
2. Extract key information like dates, weights, certification numbers, company names
3. Return a JSON response with: type, confidence (0-1), and extractedData object

Be precise. If unsure, use "other" with lower confidence.`
        },
        {
          role: 'user',
          content: [
            {
              type: 'image_url',
              image_url: {
                url: `data:${mimeType};base64,${base64Data}`
              }
            },
            {
              type: 'text',
              text: 'Classify this document and extract key information. Return only valid JSON.'
            }
          ]
        }
      ]
    });

    const content = response.choices[0].message.content;

    // Parse JSON from response
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const result = JSON.parse(jsonMatch[0]);
      return {
        type: result.type || 'other',
        confidence: result.confidence || 0.5,
        extractedData: result.extractedData || {}
      };
    }

    return { type: 'other', confidence: 0.3, extractedData: {} };
  } catch (error) {
    logger.error('AI categorization error:', error);
    return { type: 'other', confidence: 0, extractedData: {} };
  }
}

// Link document to requirement
async function linkDocumentToRequirement(documentId, jobId, documentType) {
  try {
    // Get job's vertical
    const { data: job } = await supabase
      .from('jobs')
      .select('vertical_id')
      .eq('id', jobId)
      .single();

    if (!job) return;

    // Find matching requirement
    const { data: requirement } = await supabase
      .from('esg_requirements')
      .select('id')
      .eq('vertical_id', job.vertical_id)
      .eq('requirement_type', 'documentation')
      .ilike('requirement_key', `%${documentType.replace('_', '%')}%`)
      .single();

    if (requirement) {
      await supabase
        .from('esg_documents')
        .update({ requirement_id: requirement.id })
        .eq('id', documentId);

      logger.info(`Document ${documentId} linked to requirement ${requirement.id}`);
    }
  } catch (error) {
    logger.warn('Failed to link document to requirement:', error);
  }
}

module.exports = router;
