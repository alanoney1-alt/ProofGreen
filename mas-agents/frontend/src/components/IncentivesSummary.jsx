/**
 * ProofGreen MAS - Incentives Summary Component
 * Displays breakdown of federal, state, and utility incentives.
 */

import React, { useState } from 'react';

const IncentivesSummary = ({ incentives, jobCost }) => {
  const [expanded, setExpanded] = useState(false);

  if (!incentives) return null;

  const {
    federalRebate = 0,
    stateRebate = 0,
    utilityRebate = 0,
    totalIncentives = 0,
    customerNetCost = 0,
    programs = [],
    co2AvoidedLbs = 0,
    kwhSavedAnnual = 0
  } = incentives;

  const savingsPercentage = jobCost > 0
    ? Math.round((totalIncentives / jobCost) * 100)
    : 0;

  return (
    <div className="incentives-summary">
      <div
        className="summary-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="header-left">
          <h3>Incentives & Savings</h3>
          <span className="savings-badge">{savingsPercentage}% savings</span>
        </div>
        <div className="header-right">
          <span className="total-amount">${totalIncentives.toLocaleString()}</span>
          <span className="expand-icon">{expanded ? '-' : '+'}</span>
        </div>
      </div>

      {/* Quick breakdown */}
      <div className="quick-breakdown">
        <div className="breakdown-bar">
          <div
            className="bar-segment federal"
            style={{ width: `${(federalRebate / totalIncentives) * 100}%` }}
            title={`Federal: $${federalRebate.toLocaleString()}`}
          />
          <div
            className="bar-segment state"
            style={{ width: `${(stateRebate / totalIncentives) * 100}%` }}
            title={`State: $${stateRebate.toLocaleString()}`}
          />
          <div
            className="bar-segment utility"
            style={{ width: `${(utilityRebate / totalIncentives) * 100}%` }}
            title={`Utility: $${utilityRebate.toLocaleString()}`}
          />
        </div>
        <div className="bar-legend">
          <LegendItem color="#3b82f6" label="Federal" amount={federalRebate} />
          <LegendItem color="#10b981" label="State" amount={stateRebate} />
          <LegendItem color="#f59e0b" label="Utility" amount={utilityRebate} />
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="expanded-details">
          {/* Program details */}
          <div className="programs-section">
            <h4>Available Programs</h4>
            {programs.map((program, index) => (
              <div key={index} className="program-card">
                <div className="program-header">
                  <span className="program-name">{program.name}</span>
                  <span className={`program-type ${program.type}`}>
                    {program.type}
                  </span>
                </div>
                <div className="program-amount">
                  ${program.amount.toLocaleString()}
                </div>
                {program.requirements && (
                  <div className="program-requirements">
                    <span className="req-label">Requirements:</span>
                    <span className="req-text">{program.requirements}</span>
                  </div>
                )}
                {program.deadline && (
                  <div className="program-deadline">
                    Apply by: {new Date(program.deadline).toLocaleDateString()}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Cost breakdown */}
          <div className="cost-section">
            <h4>Cost Breakdown</h4>
            <div className="cost-row">
              <span>Job Total</span>
              <span className="cost-value">${jobCost?.toLocaleString() || '0'}</span>
            </div>
            <div className="cost-row highlight">
              <span>Total Incentives</span>
              <span className="cost-value negative">-${totalIncentives.toLocaleString()}</span>
            </div>
            <div className="cost-row total">
              <span>Customer Net Cost</span>
              <span className="cost-value">${customerNetCost.toLocaleString()}</span>
            </div>
          </div>

          {/* Environmental impact */}
          <div className="impact-section">
            <h4>Environmental Impact</h4>
            <div className="impact-grid">
              <div className="impact-card">
                <span className="impact-icon">leaf</span>
                <span className="impact-value">{co2AvoidedLbs.toLocaleString()}</span>
                <span className="impact-label">lbs CO2 avoided/year</span>
              </div>
              <div className="impact-card">
                <span className="impact-icon">bolt</span>
                <span className="impact-value">{kwhSavedAnnual.toLocaleString()}</span>
                <span className="impact-label">kWh saved/year</span>
              </div>
            </div>
          </div>

          {/* Disclaimer */}
          <div className="disclaimer">
            <strong>Note:</strong> Incentive amounts are estimates based on current programs.
            Actual amounts may vary based on eligibility verification and program availability.
          </div>
        </div>
      )}

      <style jsx>{`
        .incentives-summary {
          background: white;
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
          border: 1px solid #e5e7eb;
        }

        .summary-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .header-left h3 {
          margin: 0;
          font-size: 14px;
          color: #374151;
        }

        .savings-badge {
          background: #d1fae5;
          color: #059669;
          padding: 4px 8px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }

        .header-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .total-amount {
          font-size: 20px;
          font-weight: 700;
          color: #10b981;
        }

        .expand-icon {
          font-size: 18px;
          color: #6b7280;
          width: 24px;
          text-align: center;
        }

        .quick-breakdown {
          margin-top: 16px;
        }

        .breakdown-bar {
          display: flex;
          height: 8px;
          border-radius: 4px;
          overflow: hidden;
          background: #f3f4f6;
        }

        .bar-segment {
          height: 100%;
          transition: width 0.3s;
        }

        .bar-segment.federal {
          background: #3b82f6;
        }

        .bar-segment.state {
          background: #10b981;
        }

        .bar-segment.utility {
          background: #f59e0b;
        }

        .bar-legend {
          display: flex;
          justify-content: space-between;
          margin-top: 8px;
        }

        .expanded-details {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #f3f4f6;
        }

        .programs-section,
        .cost-section,
        .impact-section {
          margin-bottom: 16px;
        }

        .programs-section h4,
        .cost-section h4,
        .impact-section h4 {
          margin: 0 0 12px 0;
          font-size: 12px;
          color: #6b7280;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .program-card {
          background: #f9fafb;
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 8px;
        }

        .program-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .program-name {
          font-weight: 500;
          color: #374151;
        }

        .program-type {
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 500;
          text-transform: uppercase;
        }

        .program-type.federal {
          background: #dbeafe;
          color: #2563eb;
        }

        .program-type.state {
          background: #d1fae5;
          color: #059669;
        }

        .program-type.utility {
          background: #fef3c7;
          color: #d97706;
        }

        .program-amount {
          font-size: 18px;
          font-weight: 600;
          color: #10b981;
          margin-bottom: 8px;
        }

        .program-requirements {
          font-size: 12px;
          color: #6b7280;
        }

        .req-label {
          font-weight: 500;
        }

        .program-deadline {
          font-size: 12px;
          color: #dc2626;
          margin-top: 4px;
        }

        .cost-row {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid #f3f4f6;
        }

        .cost-row.highlight {
          color: #10b981;
        }

        .cost-row.total {
          border-bottom: none;
          font-weight: 600;
          font-size: 16px;
          padding-top: 12px;
        }

        .cost-value {
          font-weight: 500;
        }

        .cost-value.negative {
          color: #10b981;
        }

        .impact-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .impact-card {
          background: #f0fdf4;
          border-radius: 8px;
          padding: 16px;
          text-align: center;
        }

        .impact-icon {
          display: block;
          font-size: 24px;
          margin-bottom: 8px;
        }

        .impact-value {
          display: block;
          font-size: 20px;
          font-weight: 700;
          color: #059669;
        }

        .impact-label {
          display: block;
          font-size: 12px;
          color: #6b7280;
          margin-top: 4px;
        }

        .disclaimer {
          font-size: 11px;
          color: #9ca3af;
          padding: 12px;
          background: #f9fafb;
          border-radius: 8px;
          margin-top: 16px;
        }

        .disclaimer strong {
          color: #6b7280;
        }
      `}</style>
    </div>
  );
};

// Legend item component
const LegendItem = ({ color, label, amount }) => (
  <div className="legend-item">
    <span className="legend-dot" style={{ backgroundColor: color }} />
    <span className="legend-label">{label}</span>
    <span className="legend-amount">${amount.toLocaleString()}</span>
    <style jsx>{`
      .legend-item {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 12px;
      }
      .legend-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
      }
      .legend-label {
        color: #6b7280;
      }
      .legend-amount {
        font-weight: 500;
        color: #374151;
      }
    `}</style>
  </div>
);

export default IncentivesSummary;
