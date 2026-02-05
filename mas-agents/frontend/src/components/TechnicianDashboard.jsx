/**
 * ProofGreen MAS - Technician Mobile Dashboard
 * Main dashboard component for field technicians.
 */

import React, { useState, useEffect, useCallback } from 'react';
import JobCard from './JobCard';
import WorkflowVisualization from './WorkflowVisualization';
import IncentivesSummary from './IncentivesSummary';
import ComplianceStatus from './ComplianceStatus';

const TechnicianDashboard = ({ technicianId, companyId }) => {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('today');
  const [stats, setStats] = useState({
    todayJobs: 0,
    completedJobs: 0,
    totalIncentives: 0,
    complianceRate: 0
  });

  // Fetch technician's jobs
  const fetchJobs = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `/api/technicians/${technicianId}/jobs?tab=${activeTab}`,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) throw new Error('Failed to fetch jobs');

      const data = await response.json();
      setJobs(data.jobs);
      setStats(data.stats);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [technicianId, activeTab]);

  useEffect(() => {
    fetchJobs();
    // Poll for updates every 30 seconds
    const interval = setInterval(fetchJobs, 30000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  // Handle job selection
  const handleJobSelect = (job) => {
    setSelectedJob(job);
  };

  // Handle photo upload for equipment
  const handlePhotoUpload = async (jobId, photoFile) => {
    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('jobId', jobId);

    try {
      const response = await fetch('/api/equipment/analyze', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      });

      if (!response.ok) throw new Error('Failed to upload photo');

      const result = await response.json();
      // Update job with analysis results
      setJobs(prev => prev.map(job =>
        job.id === jobId
          ? { ...job, equipmentAnalysis: result.analysis }
          : job
      ));

      return result;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  // Handle feedback submission (lessons learned)
  const handleFeedbackSubmit = async (jobId, feedback) => {
    try {
      const response = await fetch('/api/lessons-learned', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          jobId,
          technicianId,
          ...feedback
        })
      });

      if (!response.ok) throw new Error('Failed to submit feedback');

      // Refresh jobs after feedback
      await fetchJobs();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="technician-dashboard">
      {/* Header with stats */}
      <header className="dashboard-header">
        <h1>ProofGreen</h1>
        <div className="stats-row">
          <StatCard
            label="Today's Jobs"
            value={stats.todayJobs}
            icon="calendar"
          />
          <StatCard
            label="Completed"
            value={stats.completedJobs}
            icon="check-circle"
          />
          <StatCard
            label="Incentives"
            value={`$${stats.totalIncentives.toLocaleString()}`}
            icon="dollar-sign"
          />
          <StatCard
            label="Compliance"
            value={`${stats.complianceRate}%`}
            icon="shield"
          />
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="tab-nav">
        <button
          className={`tab-btn ${activeTab === 'today' ? 'active' : ''}`}
          onClick={() => setActiveTab('today')}
        >
          Today
        </button>
        <button
          className={`tab-btn ${activeTab === 'upcoming' ? 'active' : ''}`}
          onClick={() => setActiveTab('upcoming')}
        >
          Upcoming
        </button>
        <button
          className={`tab-btn ${activeTab === 'completed' ? 'active' : ''}`}
          onClick={() => setActiveTab('completed')}
        >
          Completed
        </button>
      </nav>

      {/* Error display */}
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* Main content */}
      <main className="dashboard-content">
        {loading ? (
          <LoadingSpinner />
        ) : selectedJob ? (
          <JobDetailView
            job={selectedJob}
            onBack={() => setSelectedJob(null)}
            onPhotoUpload={handlePhotoUpload}
            onFeedbackSubmit={handleFeedbackSubmit}
          />
        ) : (
          <div className="jobs-list">
            {jobs.length === 0 ? (
              <EmptyState message={`No ${activeTab} jobs`} />
            ) : (
              jobs.map(job => (
                <JobCard
                  key={job.id}
                  job={job}
                  onClick={() => handleJobSelect(job)}
                />
              ))
            )}
          </div>
        )}
      </main>

      {/* Bottom navigation */}
      <nav className="bottom-nav">
        <NavButton icon="home" label="Dashboard" active />
        <NavButton icon="camera" label="Scan" />
        <NavButton icon="file-text" label="Reports" />
        <NavButton icon="user" label="Profile" />
      </nav>

      <style jsx>{`
        .technician-dashboard {
          display: flex;
          flex-direction: column;
          min-height: 100vh;
          background: #f5f7fa;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .dashboard-header {
          background: linear-gradient(135deg, #10b981 0%, #059669 100%);
          color: white;
          padding: 16px 20px;
        }

        .dashboard-header h1 {
          font-size: 24px;
          margin: 0 0 16px 0;
        }

        .stats-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 8px;
        }

        .tab-nav {
          display: flex;
          background: white;
          padding: 8px;
          gap: 8px;
          border-bottom: 1px solid #e5e7eb;
        }

        .tab-btn {
          flex: 1;
          padding: 10px;
          border: none;
          background: #f3f4f6;
          border-radius: 8px;
          font-weight: 500;
          color: #6b7280;
          cursor: pointer;
          transition: all 0.2s;
        }

        .tab-btn.active {
          background: #10b981;
          color: white;
        }

        .error-banner {
          background: #fef2f2;
          border-left: 4px solid #ef4444;
          padding: 12px 16px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .error-banner button {
          background: none;
          border: none;
          color: #ef4444;
          cursor: pointer;
        }

        .dashboard-content {
          flex: 1;
          padding: 16px;
          overflow-y: auto;
          padding-bottom: 80px;
        }

        .jobs-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .bottom-nav {
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          background: white;
          display: flex;
          justify-content: space-around;
          padding: 8px 0 max(8px, env(safe-area-inset-bottom));
          border-top: 1px solid #e5e7eb;
          box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        }
      `}</style>
    </div>
  );
};

// Stat card component
const StatCard = ({ label, value, icon }) => (
  <div className="stat-card">
    <span className="stat-value">{value}</span>
    <span className="stat-label">{label}</span>
    <style jsx>{`
      .stat-card {
        background: rgba(255,255,255,0.15);
        border-radius: 8px;
        padding: 8px;
        text-align: center;
      }
      .stat-value {
        display: block;
        font-size: 18px;
        font-weight: 700;
      }
      .stat-label {
        font-size: 10px;
        opacity: 0.9;
      }
    `}</style>
  </div>
);

// Loading spinner
const LoadingSpinner = () => (
  <div className="loading-spinner">
    <div className="spinner" />
    <style jsx>{`
      .loading-spinner {
        display: flex;
        justify-content: center;
        padding: 40px;
      }
      .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid #e5e7eb;
        border-top-color: #10b981;
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
    `}</style>
  </div>
);

// Empty state
const EmptyState = ({ message }) => (
  <div className="empty-state">
    <div className="empty-icon">-</div>
    <p>{message}</p>
    <style jsx>{`
      .empty-state {
        text-align: center;
        padding: 40px 20px;
        color: #6b7280;
      }
      .empty-icon {
        font-size: 48px;
        margin-bottom: 16px;
      }
    `}</style>
  </div>
);

// Navigation button
const NavButton = ({ icon, label, active }) => (
  <button className={`nav-btn ${active ? 'active' : ''}`}>
    <span className="nav-icon">{icon}</span>
    <span className="nav-label">{label}</span>
    <style jsx>{`
      .nav-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        background: none;
        border: none;
        padding: 8px 16px;
        color: #6b7280;
        cursor: pointer;
      }
      .nav-btn.active {
        color: #10b981;
      }
      .nav-label {
        font-size: 12px;
      }
    `}</style>
  </button>
);

// Job detail view
const JobDetailView = ({ job, onBack, onPhotoUpload, onFeedbackSubmit }) => (
  <div className="job-detail">
    <button className="back-btn" onClick={onBack}>
      &larr; Back to Jobs
    </button>

    <div className="job-header">
      <h2>{job.jobType}</h2>
      <span className={`status-badge ${job.status}`}>{job.status}</span>
    </div>

    <div className="customer-info">
      <h3>Customer</h3>
      <p>{job.customerName}</p>
      <p>{job.address}</p>
    </div>

    {job.workflowStatus && (
      <WorkflowVisualization
        workflowId={job.workflowId}
        status={job.workflowStatus}
        currentNode={job.currentNode}
      />
    )}

    {job.equipmentAnalysis && (
      <ComplianceStatus analysis={job.equipmentAnalysis} />
    )}

    {job.incentives && (
      <IncentivesSummary incentives={job.incentives} />
    )}

    {/* Photo upload section */}
    <div className="photo-section">
      <h3>Equipment Photos</h3>
      <input
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => onPhotoUpload(job.id, e.target.files[0])}
      />
    </div>

    {/* Feedback section */}
    {job.status === 'completed' && (
      <FeedbackForm
        jobId={job.id}
        onSubmit={onFeedbackSubmit}
      />
    )}

    <style jsx>{`
      .job-detail {
        background: white;
        border-radius: 12px;
        padding: 16px;
      }
      .back-btn {
        background: none;
        border: none;
        color: #10b981;
        font-size: 14px;
        cursor: pointer;
        margin-bottom: 16px;
      }
      .job-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
      }
      .job-header h2 {
        margin: 0;
        font-size: 20px;
      }
      .status-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 500;
      }
      .status-badge.completed {
        background: #d1fae5;
        color: #059669;
      }
      .status-badge.in_progress {
        background: #fef3c7;
        color: #d97706;
      }
      .customer-info {
        margin-bottom: 16px;
        padding-bottom: 16px;
        border-bottom: 1px solid #e5e7eb;
      }
      .customer-info h3 {
        font-size: 14px;
        color: #6b7280;
        margin: 0 0 8px 0;
      }
      .customer-info p {
        margin: 4px 0;
      }
      .photo-section {
        margin-top: 16px;
        padding: 16px;
        background: #f9fafb;
        border-radius: 8px;
      }
      .photo-section h3 {
        margin: 0 0 12px 0;
        font-size: 14px;
      }
    `}</style>
  </div>
);

// Feedback form for lessons learned
const FeedbackForm = ({ jobId, onSubmit }) => {
  const [fieldOverridden, setFieldOverridden] = useState('');
  const [originalValue, setOriginalValue] = useState('');
  const [correctedValue, setCorrectedValue] = useState('');
  const [reason, setReason] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(jobId, {
      fieldOverridden,
      originalValue,
      correctedValue,
      reason
    });
    // Reset form
    setFieldOverridden('');
    setOriginalValue('');
    setCorrectedValue('');
    setReason('');
  };

  return (
    <form className="feedback-form" onSubmit={handleSubmit}>
      <h3>Submit Correction</h3>
      <p className="form-description">
        Help improve our AI by reporting any corrections you made
      </p>

      <select
        value={fieldOverridden}
        onChange={(e) => setFieldOverridden(e.target.value)}
        required
      >
        <option value="">Select field corrected</option>
        <option value="refrigerant">Refrigerant Type</option>
        <option value="seer_rating">SEER Rating</option>
        <option value="equipment_type">Equipment Type</option>
        <option value="incentive_amount">Incentive Amount</option>
        <option value="compliance_status">Compliance Status</option>
      </select>

      <input
        type="text"
        placeholder="Original AI value"
        value={originalValue}
        onChange={(e) => setOriginalValue(e.target.value)}
        required
      />

      <input
        type="text"
        placeholder="Your corrected value"
        value={correctedValue}
        onChange={(e) => setCorrectedValue(e.target.value)}
        required
      />

      <textarea
        placeholder="Why was this correction needed?"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        required
      />

      <button type="submit">Submit Feedback</button>

      <style jsx>{`
        .feedback-form {
          margin-top: 16px;
          padding: 16px;
          background: #fffbeb;
          border-radius: 8px;
          border: 1px solid #fcd34d;
        }
        .feedback-form h3 {
          margin: 0 0 8px 0;
          font-size: 16px;
        }
        .form-description {
          font-size: 12px;
          color: #6b7280;
          margin: 0 0 12px 0;
        }
        .feedback-form select,
        .feedback-form input,
        .feedback-form textarea {
          width: 100%;
          padding: 10px;
          margin-bottom: 8px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          font-size: 14px;
        }
        .feedback-form textarea {
          min-height: 80px;
          resize: vertical;
        }
        .feedback-form button {
          width: 100%;
          padding: 12px;
          background: #10b981;
          color: white;
          border: none;
          border-radius: 6px;
          font-weight: 500;
          cursor: pointer;
        }
      `}</style>
    </form>
  );
};

export default TechnicianDashboard;
