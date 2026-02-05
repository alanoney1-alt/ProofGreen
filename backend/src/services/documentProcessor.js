/**
 * Document Processing Service
 * Handles uploads, OCR, and data extraction
 */

const Anthropic = require('@anthropic-ai/sdk');
const path = require('path');
const fs = require('fs');

// Initialize Anthropic client for document analysis
const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY
});

/**
 * Document types and their expected fields for extraction
 */
const DOCUMENT_TYPES = {
  invoice: {
    name: 'Invoice/Receipt',
    fields: ['vendor_name', 'date', 'total_amount', 'items', 'tax', 'payment_method']
  },
  refrigerant_manifest: {
    name: 'Refrigerant Manifest',
    fields: ['refrigerant_type', 'quantity_lbs', 'technician_name', 'epa_cert_number', 'date', 'serial_numbers']
  },
  disposal_certificate: {
    name: 'Disposal Certificate',
    fields: ['facility_name', 'date', 'material_type', 'weight', 'manifest_number', 'certifications']
  },
  epa_certification: {
    name: 'EPA Certification',
    fields: ['cert_type', 'cert_number', 'holder_name', 'issue_date', 'expiry_date']
  },
  permit: {
    name: 'Permit',
    fields: ['permit_number', 'permit_type', 'issue_date', 'expiry_date', 'jurisdiction', 'conditions']
  },
  safety_data_sheet: {
    name: 'Safety Data Sheet (SDS)',
    fields: ['product_name', 'manufacturer', 'hazard_classification', 'active_ingredients', 'signal_word', 'first_aid']
  },
  energy_guide: {
    name: 'EnergyGuide Label',
    fields: ['appliance_type', 'brand', 'model', 'annual_kwh', 'estimated_yearly_cost', 'energy_star']
  },
  utility_bill: {
    name: 'Utility Bill',
    fields: ['utility_company', 'account_number', 'billing_period', 'kwh_used', 'total_amount', 'rate']
  },
  vehicle_registration: {
    name: 'Vehicle Registration',
    fields: ['vin', 'make', 'model', 'year', 'license_plate', 'owner_name', 'registration_date']
  },
  recycling_certificate: {
    name: 'Recycling Certificate',
    fields: ['facility_name', 'date', 'material_type', 'weight', 'certificate_number']
  }
};

/**
 * Analyze document using Claude Vision
 */
async function analyzeDocument(imageBase64, documentType, mimeType = 'image/jpeg') {
  const docConfig = DOCUMENT_TYPES[documentType] || DOCUMENT_TYPES.invoice;

  const prompt = `You are analyzing a ${docConfig.name}. Extract the following information if present:

Fields to extract: ${docConfig.fields.join(', ')}

Please respond in JSON format with the following structure:
{
  "document_type": "${documentType}",
  "confidence": 0.0 to 1.0,
  "extracted_data": {
    // field: value pairs
  },
  "raw_text": "Full text content of the document",
  "warnings": ["Any issues or unclear items"],
  "esg_relevant_data": {
    // Any ESG-relevant information found
  }
}

Be precise with numbers, dates, and technical specifications. If a field is not present or unclear, set it to null.`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mimeType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: prompt
            }
          ]
        }
      ]
    });

    // Parse the response
    const content = response.content[0].text;

    // Try to parse as JSON
    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (parseError) {
      console.error('Failed to parse OCR response as JSON:', parseError);
    }

    return {
      document_type: documentType,
      confidence: 0.5,
      raw_text: content,
      extracted_data: {},
      warnings: ['Could not parse structured data']
    };

  } catch (error) {
    console.error('Document analysis error:', error);
    throw error;
  }
}

/**
 * Extract ESG-relevant data from any document
 */
async function extractESGData(imageBase64, mimeType = 'image/jpeg') {
  const prompt = `Analyze this document and extract any ESG (Environmental, Social, Governance) relevant information.

Look for:
- Energy usage/efficiency data (kWh, BTU, SEER ratings, etc.)
- Water usage (gallons, GPM, GPF)
- Emissions data (CO2, refrigerants, GWP values)
- Chemical/material information (types, quantities, safety data)
- Certifications (ENERGY STAR, EPA, Green Seal, etc.)
- Waste/recycling information
- Fuel consumption
- Equipment specifications affecting energy/emissions

Respond in JSON format:
{
  "document_summary": "Brief description",
  "esg_category": "energy|water|emissions|materials|waste|certification|other",
  "metrics_found": [
    {
      "metric_type": "type",
      "value": number,
      "unit": "unit",
      "context": "where/what this applies to"
    }
  ],
  "certifications": ["list of certifications found"],
  "compliance_relevant": true/false,
  "regulatory_references": ["any regulations mentioned"],
  "carbon_impact": {
    "type": "positive|negative|neutral",
    "estimated_co2_lbs": number or null,
    "notes": "explanation"
  }
}`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mimeType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: prompt
            }
          ]
        }
      ]
    });

    const content = response.content[0].text;

    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (parseError) {
      console.error('Failed to parse ESG extraction as JSON:', parseError);
    }

    return {
      document_summary: 'Could not extract structured ESG data',
      raw_analysis: content
    };

  } catch (error) {
    console.error('ESG extraction error:', error);
    throw error;
  }
}

/**
 * Process invoice and extract line items with environmental data
 */
async function processInvoice(imageBase64, mimeType = 'image/jpeg') {
  const prompt = `Analyze this invoice/receipt and extract:

1. Vendor/Supplier information
2. All line items with:
   - Description
   - Quantity
   - Unit
   - Unit price
   - Total price
   - Any product codes/SKUs
3. For each item, identify if it's:
   - A material (pipe, wire, chemical, etc.)
   - Equipment (HVAC unit, water heater, etc.)
   - Labor
   - Disposal/recycling fee
   - Other

4. Flag any items with ESG relevance:
   - Energy efficiency ratings
   - Refrigerant types
   - Chemical products (EPA reg numbers)
   - Recycled/sustainable materials
   - Hazardous materials

Respond in JSON:
{
  "vendor": {
    "name": "",
    "address": "",
    "phone": ""
  },
  "invoice_number": "",
  "date": "",
  "line_items": [
    {
      "description": "",
      "quantity": 0,
      "unit": "",
      "unit_price": 0,
      "total": 0,
      "category": "material|equipment|labor|disposal|other",
      "product_code": "",
      "esg_flags": []
    }
  ],
  "subtotal": 0,
  "tax": 0,
  "total": 0,
  "esg_summary": {
    "materials_with_esg_data": [],
    "equipment_efficiency_data": [],
    "chemicals_found": [],
    "recycling_disposal_items": []
  }
}`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mimeType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: prompt
            }
          ]
        }
      ]
    });

    const content = response.content[0].text;

    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (parseError) {
      console.error('Failed to parse invoice as JSON:', parseError);
    }

    return { raw_text: content, parse_error: true };

  } catch (error) {
    console.error('Invoice processing error:', error);
    throw error;
  }
}

/**
 * Read equipment label/nameplate
 */
async function readEquipmentLabel(imageBase64, equipmentType, mimeType = 'image/jpeg') {
  const prompt = `Analyze this ${equipmentType} equipment label/nameplate and extract all specifications:

Look for:
- Brand/Manufacturer
- Model number
- Serial number
- Manufacturing date
- Capacity/Size (BTU, tons, gallons, etc.)
- Efficiency ratings (SEER, EER, HSPF, AFUE, UEF, etc.)
- Voltage/Amperage/Wattage
- Refrigerant type and charge
- ENERGY STAR certification
- Safety certifications (UL, CSA, etc.)
- Any EPA or regulatory numbers

Respond in JSON:
{
  "equipment_type": "${equipmentType}",
  "brand": "",
  "model_number": "",
  "serial_number": "",
  "manufacture_date": "",
  "specifications": {
    // All specs found
  },
  "efficiency_ratings": {
    // All efficiency data
  },
  "refrigerant": {
    "type": "",
    "charge_oz": 0,
    "gwp": 0
  },
  "certifications": [],
  "electrical": {
    "voltage": "",
    "amperage": 0,
    "wattage": 0,
    "phase": ""
  },
  "regulatory_numbers": {}
}`;

  try {
    const response = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mimeType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: prompt
            }
          ]
        }
      ]
    });

    const content = response.content[0].text;

    try {
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (parseError) {
      console.error('Failed to parse equipment label as JSON:', parseError);
    }

    return { raw_text: content, parse_error: true };

  } catch (error) {
    console.error('Equipment label reading error:', error);
    throw error;
  }
}

/**
 * Supported MIME types for upload
 */
const SUPPORTED_MIME_TYPES = [
  'image/jpeg',
  'image/png',
  'image/gif',
  'image/webp',
  'application/pdf'
];

/**
 * Validate uploaded file
 */
function validateUpload(file) {
  const errors = [];

  if (!file) {
    errors.push('No file provided');
    return { valid: false, errors };
  }

  // Check mime type
  if (!SUPPORTED_MIME_TYPES.includes(file.mimetype)) {
    errors.push(`Unsupported file type: ${file.mimetype}. Supported: ${SUPPORTED_MIME_TYPES.join(', ')}`);
  }

  // Check file size (max 10MB)
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    errors.push(`File too large: ${(file.size / 1024 / 1024).toFixed(2)}MB. Max: 10MB`);
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

module.exports = {
  DOCUMENT_TYPES,
  analyzeDocument,
  extractESGData,
  processInvoice,
  readEquipmentLabel,
  validateUpload,
  SUPPORTED_MIME_TYPES
};
