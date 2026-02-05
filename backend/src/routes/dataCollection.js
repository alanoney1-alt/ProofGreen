/**
 * Data Collection API Routes
 * Equipment, materials, chemicals, mileage, documents
 */

const express = require('express');
const router = express.Router();
const multer = require('multer');
const { createClient } = require('@supabase/supabase-js');
const mileageCalculator = require('../services/mileageCalculator');
const documentProcessor = require('../services/documentProcessor');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Configure multer for file uploads
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 } // 10MB
});

// ==========================================
// EQUIPMENT ROUTES
// ==========================================

/**
 * Search equipment models
 */
router.get('/equipment/search', async (req, res) => {
  try {
    const { q, category, manufacturer, limit = 20 } = req.query;

    let query = supabase
      .from('equipment_models')
      .select(`
        *,
        manufacturer:manufacturers(name, sustainability_rating)
      `)
      .limit(parseInt(limit));

    if (q) {
      query = query.or(`model_number.ilike.%${q}%,model_name.ilike.%${q}%`);
    }

    if (category) {
      query = query.eq('category', category);
    }

    if (manufacturer) {
      query = query.eq('manufacturer_id', manufacturer);
    }

    const { data, error } = await query;
    if (error) throw error;

    res.json({ success: true, equipment: data });
  } catch (error) {
    console.error('Equipment search error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get equipment by model number
 */
router.get('/equipment/model/:modelNumber', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('equipment_models')
      .select(`
        *,
        manufacturer:manufacturers(*)
      `)
      .eq('model_number', req.params.modelNumber)
      .single();

    if (error && error.code !== 'PGRST116') throw error;

    if (!data) {
      return res.status(404).json({ success: false, error: 'Equipment not found' });
    }

    res.json({ success: true, equipment: data });
  } catch (error) {
    console.error('Equipment lookup error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get equipment categories
 */
router.get('/equipment/categories', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('equipment_models')
      .select('category, subcategory')
      .order('category');

    if (error) throw error;

    // Get unique categories with subcategories
    const categories = {};
    data.forEach(item => {
      if (!categories[item.category]) {
        categories[item.category] = new Set();
      }
      if (item.subcategory) {
        categories[item.category].add(item.subcategory);
      }
    });

    const result = Object.entries(categories).map(([category, subcats]) => ({
      category,
      subcategories: Array.from(subcats)
    }));

    res.json({ success: true, categories: result });
  } catch (error) {
    console.error('Categories error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get manufacturers
 */
router.get('/manufacturers', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('manufacturers')
      .select('*')
      .order('name');

    if (error) throw error;
    res.json({ success: true, manufacturers: data });
  } catch (error) {
    console.error('Manufacturers error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// REFRIGERANT ROUTES
// ==========================================

/**
 * Get all refrigerants
 */
router.get('/refrigerants', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('refrigerants')
      .select('*')
      .order('epa_designation');

    if (error) throw error;
    res.json({ success: true, refrigerants: data });
  } catch (error) {
    console.error('Refrigerants error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get refrigerant by designation
 */
router.get('/refrigerants/:designation', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('refrigerants')
      .select('*')
      .eq('epa_designation', req.params.designation)
      .single();

    if (error && error.code !== 'PGRST116') throw error;

    if (!data) {
      return res.status(404).json({ success: false, error: 'Refrigerant not found' });
    }

    res.json({ success: true, refrigerant: data });
  } catch (error) {
    console.error('Refrigerant lookup error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// CHEMICALS ROUTES
// ==========================================

/**
 * Search chemicals
 */
router.get('/chemicals/search', async (req, res) => {
  try {
    const { q, category, organic_only, limit = 20 } = req.query;

    let query = supabase
      .from('chemicals')
      .select(`
        *,
        manufacturer:manufacturers(name)
      `)
      .limit(parseInt(limit));

    if (q) {
      query = query.or(`name.ilike.%${q}%,epa_registration_number.ilike.%${q}%`);
    }

    if (category) {
      query = query.eq('category', category);
    }

    if (organic_only === 'true') {
      query = query.eq('organic_certified', true);
    }

    const { data, error } = await query;
    if (error) throw error;

    res.json({ success: true, chemicals: data });
  } catch (error) {
    console.error('Chemical search error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get chemical by EPA registration number
 */
router.get('/chemicals/epa/:regNumber', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('chemicals')
      .select(`
        *,
        manufacturer:manufacturers(*)
      `)
      .eq('epa_registration_number', req.params.regNumber)
      .single();

    if (error && error.code !== 'PGRST116') throw error;

    if (!data) {
      return res.status(404).json({ success: false, error: 'Chemical not found' });
    }

    res.json({ success: true, chemical: data });
  } catch (error) {
    console.error('Chemical lookup error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// MATERIALS ROUTES
// ==========================================

/**
 * Search materials
 */
router.get('/materials/search', async (req, res) => {
  try {
    const { q, category, recyclable_only, limit = 20 } = req.query;

    let query = supabase
      .from('materials')
      .select('*')
      .limit(parseInt(limit));

    if (q) {
      query = query.or(`name.ilike.%${q}%,material_type.ilike.%${q}%`);
    }

    if (category) {
      query = query.eq('category', category);
    }

    if (recyclable_only === 'true') {
      query = query.eq('recyclable', true);
    }

    const { data, error } = await query;
    if (error) throw error;

    res.json({ success: true, materials: data });
  } catch (error) {
    console.error('Materials search error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get material categories
 */
router.get('/materials/categories', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('materials')
      .select('category, subcategory')
      .order('category');

    if (error) throw error;

    const categories = {};
    data.forEach(item => {
      if (!categories[item.category]) {
        categories[item.category] = new Set();
      }
      if (item.subcategory) {
        categories[item.category].add(item.subcategory);
      }
    });

    const result = Object.entries(categories).map(([category, subcats]) => ({
      category,
      subcategories: Array.from(subcats)
    }));

    res.json({ success: true, categories: result });
  } catch (error) {
    console.error('Material categories error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// MILEAGE/TRIP ROUTES
// ==========================================

/**
 * Calculate trip emissions
 */
router.post('/trips/calculate', async (req, res) => {
  try {
    const { distanceMiles, vehicleType, fuelType, mpg } = req.body;

    if (!distanceMiles || !vehicleType || !fuelType) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: distanceMiles, vehicleType, fuelType'
      });
    }

    const result = mileageCalculator.calculateTripEmissions(
      parseFloat(distanceMiles),
      vehicleType,
      fuelType,
      mpg ? parseFloat(mpg) : null
    );

    const offset = mileageCalculator.calculateCarbonOffset(result.co2EmissionsLbs);

    res.json({
      success: true,
      trip: result,
      offset
    });
  } catch (error) {
    console.error('Trip calculation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Calculate multiple trips (job with multiple vehicles)
 */
router.post('/trips/calculate-job', async (req, res) => {
  try {
    const { trips } = req.body;

    if (!trips || !Array.isArray(trips)) {
      return res.status(400).json({
        success: false,
        error: 'trips array is required'
      });
    }

    const result = mileageCalculator.calculateJobTripEmissions(trips);
    const offset = mileageCalculator.calculateCarbonOffset(result.totals.co2EmissionsLbs);

    res.json({
      success: true,
      ...result,
      offset
    });
  } catch (error) {
    console.error('Job trips calculation error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Estimate annual impact for recurring service
 */
router.post('/trips/estimate-annual', async (req, res) => {
  try {
    const { tripDistanceMiles, frequency, vehicleType, fuelType } = req.body;

    if (!tripDistanceMiles || !frequency || !vehicleType || !fuelType) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields'
      });
    }

    const result = mileageCalculator.estimateAnnualMileageImpact(
      parseFloat(tripDistanceMiles),
      frequency,
      vehicleType,
      fuelType
    );

    const offset = mileageCalculator.calculateCarbonOffset(result.annualCO2Lbs);

    res.json({
      success: true,
      ...result,
      offset
    });
  } catch (error) {
    console.error('Annual estimate error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get fuel emission factors
 */
router.get('/trips/emission-factors', (req, res) => {
  res.json({
    success: true,
    fuelEmissionFactors: mileageCalculator.FUEL_EMISSION_FACTORS,
    defaultMPG: mileageCalculator.DEFAULT_MPG
  });
});

// ==========================================
// VEHICLE ROUTES
// ==========================================

/**
 * Get company vehicles
 */
router.get('/vehicles/:companyId', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('vehicles')
      .select('*')
      .eq('company_id', req.params.companyId)
      .order('created_at', { ascending: false });

    if (error) throw error;
    res.json({ success: true, vehicles: data });
  } catch (error) {
    console.error('Vehicles error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Add/update vehicle
 */
router.post('/vehicles', async (req, res) => {
  try {
    const vehicleData = req.body;

    const { data, error } = await supabase
      .from('vehicles')
      .upsert(vehicleData)
      .select()
      .single();

    if (error) throw error;
    res.json({ success: true, vehicle: data });
  } catch (error) {
    console.error('Vehicle save error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// ==========================================
// DOCUMENT PROCESSING ROUTES
// ==========================================

/**
 * Upload and process document
 */
router.post('/documents/upload', upload.single('file'), async (req, res) => {
  try {
    const validation = documentProcessor.validateUpload(req.file);
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        errors: validation.errors
      });
    }

    const { documentType, jobId, companyId } = req.body;

    // Convert to base64
    const base64 = req.file.buffer.toString('base64');

    // Process with OCR
    let extractedData = null;
    if (documentType) {
      extractedData = await documentProcessor.analyzeDocument(
        base64,
        documentType,
        req.file.mimetype
      );
    } else {
      extractedData = await documentProcessor.extractESGData(
        base64,
        req.file.mimetype
      );
    }

    // Store in database (in production, upload to cloud storage first)
    const { data: doc, error } = await supabase
      .from('job_documents')
      .insert({
        job_id: jobId || null,
        company_id: companyId,
        document_type: documentType || 'unknown',
        title: req.file.originalname,
        file_name: req.file.originalname,
        file_size_bytes: req.file.size,
        mime_type: req.file.mimetype,
        file_url: `data:${req.file.mimetype};base64,${base64.substring(0, 100)}...`, // Placeholder
        ocr_processed: true,
        ocr_extracted_data: extractedData,
        ocr_confidence: extractedData?.confidence || 0.5
      })
      .select()
      .single();

    if (error) throw error;

    res.json({
      success: true,
      document: doc,
      extractedData
    });
  } catch (error) {
    console.error('Document upload error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Process invoice
 */
router.post('/documents/process-invoice', upload.single('file'), async (req, res) => {
  try {
    const validation = documentProcessor.validateUpload(req.file);
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        errors: validation.errors
      });
    }

    const base64 = req.file.buffer.toString('base64');
    const result = await documentProcessor.processInvoice(base64, req.file.mimetype);

    res.json({
      success: true,
      invoice: result
    });
  } catch (error) {
    console.error('Invoice processing error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Read equipment label
 */
router.post('/documents/read-equipment', upload.single('file'), async (req, res) => {
  try {
    const validation = documentProcessor.validateUpload(req.file);
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        errors: validation.errors
      });
    }

    const { equipmentType } = req.body;
    const base64 = req.file.buffer.toString('base64');
    const result = await documentProcessor.readEquipmentLabel(
      base64,
      equipmentType || 'unknown',
      req.file.mimetype
    );

    res.json({
      success: true,
      equipment: result
    });
  } catch (error) {
    console.error('Equipment label reading error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get document types
 */
router.get('/documents/types', (req, res) => {
  res.json({
    success: true,
    documentTypes: documentProcessor.DOCUMENT_TYPES,
    supportedMimeTypes: documentProcessor.SUPPORTED_MIME_TYPES
  });
});

// ==========================================
// FORM CONFIGURATION ROUTES
// ==========================================

/**
 * Get form configuration for a vertical
 */
router.get('/forms/:verticalSlug', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('vertical_form_config')
      .select(`
        *,
        vertical:verticals(id, name, slug, icon)
      `)
      .eq('vertical.slug', req.params.verticalSlug)
      .single();

    if (error && error.code !== 'PGRST116') throw error;

    if (!data) {
      return res.status(404).json({
        success: false,
        error: 'Form configuration not found for this vertical'
      });
    }

    res.json({
      success: true,
      formConfig: data
    });
  } catch (error) {
    console.error('Form config error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

/**
 * Get all form configurations
 */
router.get('/forms', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('vertical_form_config')
      .select(`
        id,
        vertical_id,
        vertical:verticals(id, name, slug, icon)
      `);

    if (error) throw error;

    res.json({
      success: true,
      forms: data
    });
  } catch (error) {
    console.error('Forms list error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

module.exports = router;
