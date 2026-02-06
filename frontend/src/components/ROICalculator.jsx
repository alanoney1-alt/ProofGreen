/**
 * ProofGreen ROI Calculator
 *
 * Interactive calculator showing potential return on investment:
 * - Contract wins with ESG documentation
 * - Premium pricing capability
 * - Time savings on reporting
 *
 * Used on marketing pages and during trials to demonstrate value.
 */

import React, { useState, useMemo } from 'react';
import PropTypes from 'prop-types';

// ProofGreen pricing tiers (annual)
const PRICING = {
  founders: { monthly: 99, annual: 1188, label: 'Founders (Limited)' },
  starter: { monthly: 149, annual: 1788, label: 'Starter' },
  professional: { monthly: 299, annual: 3588, label: 'Professional' },
  business: { monthly: 599, annual: 7188, label: 'Business' },
  enterprise: { monthly: 1999, annual: 23988, label: 'Enterprise' }
};

// Default assumptions for ROI calculation
const DEFAULTS = {
  revenue: 500000,
  contracts: 1,
  contractValue: 50000,
  hoursOnReporting: 10, // hours per month
  hourlyRate: 50
};

// ROI multipliers (based on customer data)
const MULTIPLIERS = {
  contractWinRate: 0.75, // 75% of estimated contract value
  premiumPricingUplift: 0.15, // 15% premium pricing possible
  timeReduction: 0.80 // 80% time savings on reporting
};

export function ROICalculator({
  variant = 'full', // 'full' | 'compact' | 'inline'
  selectedPlan = 'professional',
  onGetStarted
}) {
  const [inputs, setInputs] = useState({
    revenue: DEFAULTS.revenue,
    contracts: DEFAULTS.contracts,
    contractValue: DEFAULTS.contractValue,
    hoursOnReporting: DEFAULTS.hoursOnReporting,
    hourlyRate: DEFAULTS.hourlyRate
  });

  const [showDetails, setShowDetails] = useState(false);

  // Calculate ROI
  const roi = useMemo(() => {
    const annualCost = PRICING[selectedPlan]?.annual || PRICING.professional.annual;

    // Contract wins benefit
    const contractsWon = inputs.contracts * inputs.contractValue * MULTIPLIERS.contractWinRate;

    // Premium pricing benefit (percentage of revenue)
    const premiumPricing = inputs.revenue * MULTIPLIERS.premiumPricingUplift;

    // Time savings benefit
    const hoursSaved = inputs.hoursOnReporting * 12 * MULTIPLIERS.timeReduction;
    const timeSavingsValue = hoursSaved * inputs.hourlyRate;

    // Total benefit
    const totalBenefit = contractsWon + premiumPricing + timeSavingsValue;

    // Net gain
    const netGain = totalBenefit - annualCost;

    // ROI multiple
    const roiMultiple = totalBenefit / annualCost;

    // Payback period (months)
    const monthlyBenefit = totalBenefit / 12;
    const monthlyCost = annualCost / 12;
    const paybackMonths = monthlyCost / monthlyBenefit * 12;

    return {
      cost: annualCost,
      contractsWon,
      premiumPricing,
      timeSavingsValue,
      hoursSaved,
      totalBenefit,
      netGain,
      roiMultiple: roiMultiple.toFixed(1),
      paybackMonths: Math.ceil(paybackMonths)
    };
  }, [inputs, selectedPlan]);

  // Input change handler
  const handleInputChange = (field, value) => {
    const numValue = parseInt(value) || 0;
    setInputs(prev => ({ ...prev, [field]: numValue }));
  };

  // Render compact version
  if (variant === 'compact') {
    return (
      <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6 border border-green-200">
        <div className="text-center">
          <div className="text-5xl font-bold text-green-600 mb-2">
            {roi.roiMultiple}x
          </div>
          <div className="text-gray-700 mb-4">Average ROI</div>
          <div className="text-sm text-gray-600">
            Based on ${inputs.revenue.toLocaleString()} annual revenue
          </div>
        </div>
        {onGetStarted && (
          <button
            onClick={onGetStarted}
            className="w-full mt-4 py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700"
          >
            Calculate Your ROI
          </button>
        )}
      </div>
    );
  }

  // Full calculator
  return (
    <div className="bg-white rounded-xl shadow-xl overflow-hidden max-w-2xl mx-auto">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-green-700 px-6 py-4 text-white">
        <h2 className="text-2xl font-bold">Will ProofGreen Pay For Itself?</h2>
        <p className="text-green-100 mt-1">
          See your potential return on investment
        </p>
      </div>

      {/* Calculator Body */}
      <div className="p-6">
        {/* Input Fields */}
        <div className="space-y-4 mb-8">
          <InputField
            label="Your annual revenue"
            value={inputs.revenue}
            onChange={(v) => handleInputChange('revenue', v)}
            prefix="$"
            hint="Total revenue from service jobs"
          />

          <InputField
            label="ESG-requiring contracts you could bid on"
            value={inputs.contracts}
            onChange={(v) => handleInputChange('contracts', v)}
            hint="Government, commercial, or corporate contracts requiring ESG documentation"
          />

          <InputField
            label="Average contract value"
            value={inputs.contractValue}
            onChange={(v) => handleInputChange('contractValue', v)}
            prefix="$"
            hint="Typical value of contracts requiring ESG data"
          />

          {/* Advanced inputs toggle */}
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="text-blue-600 text-sm hover:underline"
          >
            {showDetails ? '- Hide advanced options' : '+ Show advanced options'}
          </button>

          {showDetails && (
            <div className="space-y-4 pt-2 border-t">
              <InputField
                label="Hours spent on ESG reporting per month"
                value={inputs.hoursOnReporting}
                onChange={(v) => handleInputChange('hoursOnReporting', v)}
                suffix="hours"
              />
              <InputField
                label="Your hourly rate"
                value={inputs.hourlyRate}
                onChange={(v) => handleInputChange('hourlyRate', v)}
                prefix="$"
                suffix="/hour"
              />
            </div>
          )}
        </div>

        {/* Results */}
        <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-500 rounded-xl p-6">
          {/* Main ROI */}
          <div className="text-center mb-6">
            <div className="text-6xl font-bold text-green-600 mb-2">
              {roi.roiMultiple}x
            </div>
            <div className="text-xl text-gray-700">Return on Investment</div>
          </div>

          {/* Breakdown */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-white rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-gray-900">
                ${roi.totalBenefit.toLocaleString()}
              </div>
              <div className="text-sm text-gray-600">Annual Benefit</div>
            </div>
            <div className="bg-white rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-gray-900">
                ${roi.cost.toLocaleString()}
              </div>
              <div className="text-sm text-gray-600">Annual Cost</div>
            </div>
          </div>

          {/* Net Gain */}
          <div className="text-center py-4 border-t border-green-200">
            <div className="text-3xl font-bold text-green-600">
              ${roi.netGain.toLocaleString()}
            </div>
            <div className="text-gray-700">Net Annual Gain</div>
          </div>

          {/* Benefit Breakdown */}
          <div className="mt-4 pt-4 border-t border-green-200">
            <h4 className="font-semibold text-gray-700 mb-3">How you benefit:</h4>
            <div className="space-y-2 text-sm">
              <BenefitRow
                label="New contracts won with ESG documentation"
                value={roi.contractsWon}
              />
              <BenefitRow
                label="Premium pricing from sustainability positioning"
                value={roi.premiumPricing}
              />
              <BenefitRow
                label={`Time saved (${roi.hoursSaved.toFixed(0)} hours/year)`}
                value={roi.timeSavingsValue}
              />
            </div>
          </div>

          {/* Payback Period */}
          <div className="mt-4 text-center text-sm text-gray-600">
            Estimated payback period: <strong>{roi.paybackMonths} months</strong>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-6">
          <button
            onClick={onGetStarted}
            className="w-full py-4 bg-green-600 text-white rounded-lg text-xl font-bold hover:bg-green-700 transition-colors"
          >
            Start Free Trial - No Credit Card Required
          </button>
          <p className="text-center text-sm text-gray-500 mt-2">
            14-day free trial | Cancel anytime
          </p>
        </div>

        {/* Assumptions note */}
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <p className="text-xs text-gray-500">
            <strong>Calculation assumptions:</strong> Contract win improvement based on
            customer surveys showing 75% attribution to ESG capabilities. Premium pricing
            uplift based on industry data for sustainability-focused businesses. Time
            savings based on average customer reporting reduction. Actual results may vary.
          </p>
        </div>
      </div>
    </div>
  );
}

// Input Field Component
function InputField({ label, value, onChange, prefix, suffix, hint }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      <div className="relative">
        {prefix && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">
            {prefix}
          </span>
        )}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full p-3 border-2 border-gray-200 rounded-lg text-lg focus:border-green-500 focus:ring-0 ${
            prefix ? 'pl-8' : ''
          } ${suffix ? 'pr-16' : ''}`}
        />
        {suffix && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500">
            {suffix}
          </span>
        )}
      </div>
      {hint && (
        <p className="text-xs text-gray-500 mt-1">{hint}</p>
      )}
    </div>
  );
}

// Benefit Row Component
function BenefitRow({ label, value }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-gray-600">{label}</span>
      <span className="font-semibold text-gray-900">
        +${value.toLocaleString()}
      </span>
    </div>
  );
}

ROICalculator.propTypes = {
  variant: PropTypes.oneOf(['full', 'compact', 'inline']),
  selectedPlan: PropTypes.string,
  onGetStarted: PropTypes.func
};

export default ROICalculator;
