/**
 * ProofGreen MAS - Compliance Status Component
 * Displays EPA AIM Act and SEER2 compliance status.
 */

import React, { useState } from 'react';

const ComplianceStatus = ({ analysis }) => {
  const [expanded, setExpanded] = useState(false);

  if (!analysis) return null;

  const {
    manufacturer,
    modelNumber,
    serialNumber,
    equipmentType,
    refrigerant,
    seerRating,
    manufactureDate,
    compliance = {}
  } = analysis;

  const {
    epaAimCompliant,
    seer2Compliant,
    issues = [],
    recommendations = []
  } = compliance;

  const overallCompliant = epaAimCompliant && seer2Compliant;

  return (
    <div className={`compliance-status ${overallCompliant ? 'compliant' : 'non-compliant'}`}>
      <div
        className="status-header"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="header-left">
          <div className={`status-icon ${overallCompliant ? 'pass' : 'fail'}`}>
            {overallCompliant ? 'checkmark' : 'warning'}
          </div>
          <div className="header-text">
            <h3>Compliance Status</h3>
            <span className="status-label">
              {overallCompliant ? '2026 Compliant' : 'Action Required'}
            </span>
          </div>
        </div>
        <span className="expand-icon">{expanded ? '-' : '+'}</span>
      </div>

      {/* Quick status badges */}
      <div className="status-badges">
        <StatusBadge
          label="EPA AIM Act"
          passed={epaAimCompliant}
          tooltip={epaAimCompliant ? 'Refrigerant compliant' : 'Refrigerant needs upgrade'}
        />
        <StatusBadge
          label="SEER2"
          passed={seer2Compliant}
          tooltip={seer2Compliant ? 'Efficiency compliant' : 'Below minimum efficiency'}
        />
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="expanded-details">
          {/* Equipment info */}
          <div className="equipment-section">
            <h4>Equipment Details</h4>
            <div className="equipment-grid">
              <InfoRow label="Manufacturer" value={manufacturer} />
              <InfoRow label="Model" value={modelNumber} />
              <InfoRow label="Serial" value={serialNumber} />
              <InfoRow label="Type" value={equipmentType} />
              <InfoRow label="Refrigerant" value={refrigerant} highlight={!epaAimCompliant} />
              <InfoRow label="SEER" value={seerRating} highlight={!seer2Compliant} />
              <InfoRow label="Manufacture Date" value={manufactureDate} />
            </div>
          </div>

          {/* Issues */}
          {issues.length > 0 && (
            <div className="issues-section">
              <h4>Compliance Issues</h4>
              <ul className="issues-list">
                {issues.map((issue, index) => (
                  <li key={index} className="issue-item">
                    <span className="issue-icon">warning</span>
                    <span className="issue-text">{issue}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div className="recommendations-section">
              <h4>Recommendations</h4>
              <ul className="recommendations-list">
                {recommendations.map((rec, index) => (
                  <li key={index} className="rec-item">
                    <span className="rec-icon">lightbulb</span>
                    <span className="rec-text">{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Regulatory info */}
          <div className="regulatory-info">
            <h4>2026 Regulatory Requirements</h4>
            <div className="reg-card">
              <div className="reg-header">
                <span className="reg-title">EPA AIM Act</span>
                <a href="https://www.epa.gov/climate-hfcs-reduction" target="_blank" rel="noopener noreferrer">
                  Learn more
                </a>
              </div>
              <p className="reg-description">
                The American Innovation and Manufacturing (AIM) Act phases down HFCs including R-410A.
                Equipment installed after 2025 must use low-GWP refrigerants like R-454B or R-32.
              </p>
            </div>
            <div className="reg-card">
              <div className="reg-header">
                <span className="reg-title">SEER2 Standards</span>
                <a href="https://www.energy.gov/eere/buildings/standards-and-test-procedures" target="_blank" rel="noopener noreferrer">
                  Learn more
                </a>
              </div>
              <p className="reg-description">
                New DOE efficiency standards require minimum SEER2 ratings:
                <br />- Northern Region: 14.3 SEER2
                <br />- Southeast/Southwest: 15.2 SEER2
              </p>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .compliance-status {
          background: white;
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
          border: 2px solid;
        }

        .compliance-status.compliant {
          border-color: #10b981;
        }

        .compliance-status.non-compliant {
          border-color: #f59e0b;
        }

        .status-header {
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

        .status-icon {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
        }

        .status-icon.pass {
          background: #d1fae5;
          color: #059669;
        }

        .status-icon.fail {
          background: #fef3c7;
          color: #d97706;
        }

        .header-text h3 {
          margin: 0;
          font-size: 14px;
          color: #374151;
        }

        .status-label {
          font-size: 12px;
          color: #6b7280;
        }

        .expand-icon {
          font-size: 18px;
          color: #6b7280;
        }

        .status-badges {
          display: flex;
          gap: 12px;
          margin-top: 16px;
        }

        .expanded-details {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #f3f4f6;
        }

        .equipment-section,
        .issues-section,
        .recommendations-section,
        .regulatory-info {
          margin-bottom: 16px;
        }

        .equipment-section h4,
        .issues-section h4,
        .recommendations-section h4,
        .regulatory-info h4 {
          margin: 0 0 12px 0;
          font-size: 12px;
          color: #6b7280;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .equipment-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
        }

        .issues-list,
        .recommendations-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .issue-item,
        .rec-item {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          padding: 8px;
          border-radius: 6px;
          margin-bottom: 4px;
        }

        .issue-item {
          background: #fef2f2;
        }

        .issue-icon {
          color: #dc2626;
        }

        .issue-text {
          color: #991b1b;
          font-size: 14px;
        }

        .rec-item {
          background: #f0fdf4;
        }

        .rec-icon {
          color: #059669;
        }

        .rec-text {
          color: #166534;
          font-size: 14px;
        }

        .reg-card {
          background: #f9fafb;
          border-radius: 8px;
          padding: 12px;
          margin-bottom: 8px;
        }

        .reg-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .reg-title {
          font-weight: 600;
          color: #374151;
        }

        .reg-header a {
          font-size: 12px;
          color: #3b82f6;
          text-decoration: none;
        }

        .reg-description {
          font-size: 13px;
          color: #6b7280;
          margin: 0;
          line-height: 1.5;
        }
      `}</style>
    </div>
  );
};

// Status badge component
const StatusBadge = ({ label, passed, tooltip }) => (
  <div className={`status-badge ${passed ? 'pass' : 'fail'}`} title={tooltip}>
    <span className="badge-icon">{passed ? 'check' : 'x'}</span>
    <span className="badge-label">{label}</span>
    <style jsx>{`
      .status-badge {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border-radius: 8px;
        flex: 1;
      }
      .status-badge.pass {
        background: #d1fae5;
      }
      .status-badge.fail {
        background: #fee2e2;
      }
      .badge-icon {
        font-size: 14px;
      }
      .status-badge.pass .badge-icon {
        color: #059669;
      }
      .status-badge.fail .badge-icon {
        color: #dc2626;
      }
      .badge-label {
        font-size: 12px;
        font-weight: 500;
      }
      .status-badge.pass .badge-label {
        color: #059669;
      }
      .status-badge.fail .badge-label {
        color: #dc2626;
      }
    `}</style>
  </div>
);

// Info row component
const InfoRow = ({ label, value, highlight }) => (
  <div className={`info-row ${highlight ? 'highlight' : ''}`}>
    <span className="info-label">{label}</span>
    <span className="info-value">{value || '-'}</span>
    <style jsx>{`
      .info-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 8px;
        border-radius: 4px;
      }
      .info-row.highlight {
        background: #fef2f2;
      }
      .info-label {
        font-size: 12px;
        color: #6b7280;
      }
      .info-value {
        font-size: 12px;
        font-weight: 500;
        color: #374151;
      }
      .info-row.highlight .info-value {
        color: #dc2626;
      }
    `}</style>
  </div>
);

export default ComplianceStatus;
