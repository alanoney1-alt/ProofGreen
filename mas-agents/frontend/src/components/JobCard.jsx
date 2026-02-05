/**
 * ProofGreen MAS - Job Card Component
 * Displays job summary for technician dashboard.
 */

import React from 'react';

const JobCard = ({ job, onClick }) => {
  const {
    id,
    jobType,
    customerName,
    address,
    scheduledTime,
    status,
    equipmentAnalysis,
    incentives,
    priority
  } = job;

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#10b981';
      case 'in_progress': return '#f59e0b';
      case 'scheduled': return '#3b82f6';
      case 'urgent': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getPriorityBadge = (priority) => {
    if (priority === 'emergency') {
      return <span className="priority-badge emergency">EMERGENCY</span>;
    }
    if (priority === 'high') {
      return <span className="priority-badge high">HIGH</span>;
    }
    return null;
  };

  const formatTime = (time) => {
    if (!time) return '';
    const date = new Date(time);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  return (
    <div className="job-card" onClick={onClick}>
      <div className="job-card-header">
        <div className="job-type-row">
          <span className="job-type">{jobType}</span>
          {getPriorityBadge(priority)}
        </div>
        <span
          className="status-indicator"
          style={{ backgroundColor: getStatusColor(status) }}
        />
      </div>

      <div className="customer-section">
        <span className="customer-name">{customerName}</span>
        <span className="address">{address}</span>
      </div>

      <div className="job-details">
        {scheduledTime && (
          <div className="detail-item">
            <span className="detail-icon">clock</span>
            <span className="detail-text">{formatTime(scheduledTime)}</span>
          </div>
        )}

        {equipmentAnalysis && (
          <div className="equipment-preview">
            <span className="equipment-type">
              {equipmentAnalysis.equipmentType || 'Equipment'}
            </span>
            {equipmentAnalysis.refrigerant && (
              <span className={`refrigerant-badge ${
                equipmentAnalysis.compliance?.epaAimCompliant ? 'compliant' : 'non-compliant'
              }`}>
                {equipmentAnalysis.refrigerant}
              </span>
            )}
          </div>
        )}
      </div>

      {incentives && (
        <div className="incentives-preview">
          <span className="incentives-label">Est. Incentives:</span>
          <span className="incentives-amount">
            ${incentives.totalIncentives?.toLocaleString() || '0'}
          </span>
        </div>
      )}

      <div className="job-card-footer">
        <span className="status-text">{status.replace('_', ' ')}</span>
        <span className="arrow">&#8250;</span>
      </div>

      <style jsx>{`
        .job-card {
          background: white;
          border-radius: 12px;
          padding: 16px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08);
          cursor: pointer;
          transition: transform 0.2s, box-shadow 0.2s;
        }

        .job-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }

        .job-card:active {
          transform: scale(0.98);
        }

        .job-card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 12px;
        }

        .job-type-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .job-type {
          font-weight: 600;
          font-size: 16px;
          color: #111827;
        }

        .priority-badge {
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.5px;
        }

        .priority-badge.emergency {
          background: #fef2f2;
          color: #dc2626;
          animation: pulse 2s infinite;
        }

        .priority-badge.high {
          background: #fef3c7;
          color: #d97706;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }

        .status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }

        .customer-section {
          margin-bottom: 12px;
        }

        .customer-name {
          display: block;
          font-weight: 500;
          color: #374151;
          margin-bottom: 4px;
        }

        .address {
          font-size: 14px;
          color: #6b7280;
        }

        .job-details {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 12px;
        }

        .detail-item {
          display: flex;
          align-items: center;
          gap: 4px;
          color: #6b7280;
          font-size: 14px;
        }

        .equipment-preview {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .equipment-type {
          font-size: 14px;
          color: #4b5563;
        }

        .refrigerant-badge {
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 12px;
          font-weight: 500;
        }

        .refrigerant-badge.compliant {
          background: #d1fae5;
          color: #059669;
        }

        .refrigerant-badge.non-compliant {
          background: #fee2e2;
          color: #dc2626;
        }

        .incentives-preview {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          background: #f0fdf4;
          border-radius: 8px;
          margin-bottom: 12px;
        }

        .incentives-label {
          font-size: 12px;
          color: #059669;
        }

        .incentives-amount {
          font-weight: 700;
          color: #059669;
          font-size: 16px;
        }

        .job-card-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 12px;
          border-top: 1px solid #f3f4f6;
        }

        .status-text {
          font-size: 12px;
          color: #6b7280;
          text-transform: capitalize;
        }

        .arrow {
          color: #9ca3af;
          font-size: 20px;
        }
      `}</style>
    </div>
  );
};

export default JobCard;
