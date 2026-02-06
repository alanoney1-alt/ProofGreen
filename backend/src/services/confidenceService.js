/**
 * ProofGreen AI Confidence Service
 *
 * Calculates confidence scores for AI photo analysis based on:
 * - Image quality assessment
 * - Scene complexity
 * - Detection certainty
 *
 * CRITICAL: All AI analyses require user verification before submission.
 */

const { logger } = require('../utils/logger');

/**
 * Confidence levels and their thresholds
 */
const CONFIDENCE_LEVELS = {
  HIGH: { min: 80, label: 'high', color: 'green', needsReview: false },
  MEDIUM: { min: 60, label: 'medium', color: 'yellow', needsReview: true },
  LOW: { min: 0, label: 'low', color: 'red', needsReview: true }
};

/**
 * Factors that reduce confidence score
 */
const CONFIDENCE_PENALTIES = {
  POOR_IMAGE_QUALITY: { weight: 30, message: 'Image quality is low - may affect accuracy' },
  BLURRY_IMAGE: { weight: 25, message: 'Image appears blurry' },
  LOW_LIGHTING: { weight: 20, message: 'Poor lighting conditions detected' },
  HIGH_CLUTTER: { weight: 20, message: 'Cluttered scene - items may overlap' },
  MANY_ITEMS: { weight: 15, message: 'Many items detected - weights are estimates' },
  PARTIAL_VISIBILITY: { weight: 20, message: 'Some items may be partially obscured' },
  UNUSUAL_ANGLES: { weight: 15, message: 'Non-standard camera angle' },
  SMALL_ITEMS: { weight: 10, message: 'Small items detected - harder to estimate weight' },
  MIXED_CATEGORIES: { weight: 10, message: 'Mixed item categories - classification uncertainty' },
  NO_SCALE_REFERENCE: { weight: 15, message: 'No size reference in image - weight estimates may vary' }
};

/**
 * Calculate comprehensive confidence score for AI analysis
 *
 * @param {Object} analysisResult - Raw AI analysis result
 * @param {Object} imageMetadata - Image quality metadata
 * @returns {Object} Confidence assessment with score, level, factors, and recommendations
 */
function calculateConfidenceScore(analysisResult, imageMetadata = {}) {
  let score = 100;
  const factors = [];
  const warnings = [];

  // Base confidence from AI's own assessment
  const aiConfidence = analysisResult.confidence || 0.85;
  if (aiConfidence < 0.7) {
    score -= 20;
    factors.push('AI model uncertainty detected');
  }

  // Image quality assessment
  if (imageMetadata.quality === 'poor' || imageMetadata.resolution < 800) {
    score -= CONFIDENCE_PENALTIES.POOR_IMAGE_QUALITY.weight;
    factors.push(CONFIDENCE_PENALTIES.POOR_IMAGE_QUALITY.message);
    warnings.push({
      type: 'image_quality',
      severity: 'high',
      message: 'Please retake photo with better quality if possible'
    });
  }

  if (imageMetadata.blurry) {
    score -= CONFIDENCE_PENALTIES.BLURRY_IMAGE.weight;
    factors.push(CONFIDENCE_PENALTIES.BLURRY_IMAGE.message);
  }

  if (imageMetadata.lighting === 'low') {
    score -= CONFIDENCE_PENALTIES.LOW_LIGHTING.weight;
    factors.push(CONFIDENCE_PENALTIES.LOW_LIGHTING.message);
  }

  // Scene complexity assessment
  const items = analysisResult.items || [];

  if (items.length > 10) {
    score -= CONFIDENCE_PENALTIES.MANY_ITEMS.weight;
    factors.push(CONFIDENCE_PENALTIES.MANY_ITEMS.message);
    warnings.push({
      type: 'item_count',
      severity: 'medium',
      message: `${items.length} items detected - please verify each item and weight`
    });
  }

  if (items.length > 15) {
    score -= 10; // Additional penalty for very cluttered scenes
  }

  // Check for overlapping/partial items in scene description
  const sceneDesc = (analysisResult.scene_description || '').toLowerCase();
  if (sceneDesc.includes('clutter') || sceneDesc.includes('pile') || sceneDesc.includes('stacked')) {
    score -= CONFIDENCE_PENALTIES.HIGH_CLUTTER.weight;
    factors.push(CONFIDENCE_PENALTIES.HIGH_CLUTTER.message);
  }

  if (sceneDesc.includes('partial') || sceneDesc.includes('obscure') || sceneDesc.includes('hidden')) {
    score -= CONFIDENCE_PENALTIES.PARTIAL_VISIBILITY.weight;
    factors.push(CONFIDENCE_PENALTIES.PARTIAL_VISIBILITY.message);
  }

  // Check for weight estimation uncertainty
  const itemsWithoutWeight = items.filter(item => !item.weight_lbs || item.weight_lbs === 0);
  if (itemsWithoutWeight.length > 0) {
    score -= 15;
    factors.push(`${itemsWithoutWeight.length} items without weight estimates`);
  }

  // Check for small items (harder to estimate weight)
  const smallItems = items.filter(item => item.weight_lbs && item.weight_lbs < 5);
  if (smallItems.length > items.length * 0.5) {
    score -= CONFIDENCE_PENALTIES.SMALL_ITEMS.weight;
    factors.push(CONFIDENCE_PENALTIES.SMALL_ITEMS.message);
  }

  // Check for mixed categories (classification uncertainty)
  const categories = [...new Set(items.map(item => item.category))];
  if (categories.length > 4) {
    score -= CONFIDENCE_PENALTIES.MIXED_CATEGORIES.weight;
    factors.push(CONFIDENCE_PENALTIES.MIXED_CATEGORIES.message);
  }

  // Ensure score stays within bounds
  score = Math.max(0, Math.min(100, score));

  // Determine confidence level
  let level;
  if (score >= CONFIDENCE_LEVELS.HIGH.min) {
    level = CONFIDENCE_LEVELS.HIGH;
  } else if (score >= CONFIDENCE_LEVELS.MEDIUM.min) {
    level = CONFIDENCE_LEVELS.MEDIUM;
  } else {
    level = CONFIDENCE_LEVELS.LOW;
  }

  // Always require verification regardless of score
  const needsReview = level.needsReview || score < 80;

  return {
    score: Math.round(score),
    level: level.label,
    color: level.color,
    factors,
    warnings,
    needsReview,
    // CRITICAL: User must ALWAYS verify before submission
    userMustVerify: true,
    recommendations: generateRecommendations(score, factors, items),
    aiSuggestions: items,
    metadata: {
      itemCount: items.length,
      categoriesDetected: categories.length,
      totalEstimatedWeight: items.reduce((sum, item) => sum + (item.weight_lbs || 0), 0),
      analysisTimestamp: new Date().toISOString()
    }
  };
}

/**
 * Generate actionable recommendations based on confidence analysis
 */
function generateRecommendations(score, factors, items) {
  const recommendations = [];

  if (score < 70) {
    recommendations.push({
      priority: 'high',
      action: 'manual_review',
      message: 'Low confidence score - carefully review ALL items and weights before submitting'
    });
  }

  if (factors.some(f => f.includes('quality') || f.includes('blurry'))) {
    recommendations.push({
      priority: 'high',
      action: 'retake_photo',
      message: 'Consider retaking photo in better conditions for more accurate analysis'
    });
  }

  if (factors.some(f => f.includes('weight'))) {
    recommendations.push({
      priority: 'high',
      action: 'verify_weights',
      message: 'Use scale or weight ticket to verify actual weights - AI estimates may vary significantly'
    });
  }

  if (items.length > 8) {
    recommendations.push({
      priority: 'medium',
      action: 'split_photos',
      message: 'Consider taking multiple photos of different areas for better accuracy'
    });
  }

  // Always add weight verification recommendation
  recommendations.push({
    priority: 'critical',
    action: 'document_weight',
    message: 'Enter actual weight from scale reading, weight ticket, or disposal receipt'
  });

  return recommendations;
}

/**
 * Analyze image metadata for quality assessment
 * Called during photo upload to pre-assess quality
 */
function assessImageQuality(imageBuffer, mimeType) {
  // Basic image quality checks
  const metadata = {
    size: imageBuffer.length,
    mimeType,
    quality: 'good',
    resolution: 1920, // Default assumption
    blurry: false,
    lighting: 'normal'
  };

  // Check file size (very small images are likely low quality)
  if (imageBuffer.length < 50000) { // Less than 50KB
    metadata.quality = 'poor';
    metadata.resolution = 640;
  } else if (imageBuffer.length < 100000) { // Less than 100KB
    metadata.quality = 'medium';
    metadata.resolution = 1024;
  }

  // Check for JPEG quality markers (simplified)
  if (mimeType === 'image/jpeg' && imageBuffer.length > 0) {
    // Very basic quality heuristic based on file size to resolution ratio
    // In production, use proper image analysis library
    const compressionRatio = imageBuffer.length / 1000000; // Assume 1MP
    if (compressionRatio < 0.05) {
      metadata.quality = 'poor';
    }
  }

  return metadata;
}

/**
 * Create user-facing confidence summary for display
 */
function formatConfidenceForDisplay(confidenceResult) {
  const statusConfig = {
    high: {
      icon: '✓',
      title: 'High Confidence',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-500',
      textColor: 'text-green-800',
      message: 'Analysis looks good. Please confirm accuracy before submitting.'
    },
    medium: {
      icon: '⚠️',
      title: 'Medium Confidence',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-500',
      textColor: 'text-yellow-800',
      message: 'Some uncertainty detected. Please review items and weights carefully.'
    },
    low: {
      icon: '❌',
      title: 'Low Confidence',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-500',
      textColor: 'text-red-800',
      message: 'Significant uncertainty. Manual verification of ALL items and weights is required.'
    }
  };

  const config = statusConfig[confidenceResult.level];

  return {
    ...confidenceResult,
    display: {
      ...config,
      scoreText: `${confidenceResult.score}%`,
      factorCount: confidenceResult.factors.length,
      warningCount: confidenceResult.warnings.length,
      // CRITICAL: Always show verification required
      verificationRequired: true,
      verificationMessage: 'You must verify all items and enter actual weight before submitting.'
    }
  };
}

module.exports = {
  calculateConfidenceScore,
  assessImageQuality,
  formatConfidenceForDisplay,
  CONFIDENCE_LEVELS,
  CONFIDENCE_PENALTIES
};
