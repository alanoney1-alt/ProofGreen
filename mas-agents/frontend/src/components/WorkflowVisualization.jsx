/**
 * ProofGreen MAS - Workflow Visualization Component
 * Visual representation of LangGraph workflow status.
 */

import React, { useState, useEffect } from 'react';

const WORKFLOW_NODES = [
  { id: 'vision_audit', label: 'Equipment Scan', icon: 'camera' },
  { id: 'compliance_check', label: 'Compliance Check', icon: 'shield' },
  { id: 'calculate_cash', label: 'Incentive Calc', icon: 'dollar' },
  { id: 'self_correction', label: 'Self-Correction', icon: 'refresh', optional: true },
  { id: 'human_gatekeeper', label: 'Approval', icon: 'user-check' },
  { id: 'finalize', label: 'Complete', icon: 'check' }
];

const WorkflowVisualization = ({ workflowId, status, currentNode, onApprove, onReject }) => {
  const [expanded, setExpanded] = useState(false);
  const [nodeDetails, setNodeDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch detailed workflow state
  const fetchWorkflowDetails = async () => {
    if (!workflowId) return;

    try {
      setLoading(true);
      const response = await fetch(`/api/workflows/${workflowId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) throw new Error('Failed to fetch workflow');

      const data = await response.json();
      setNodeDetails(data.nodeDetails);
    } catch (err) {
      console.error('Error fetching workflow:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (expanded) {
      fetchWorkflowDetails();
    }
  }, [expanded, workflowId]);

  const getNodeStatus = (nodeId) => {
    const currentIndex = WORKFLOW_NODES.findIndex(n => n.id === currentNode);
    const nodeIndex = WORKFLOW_NODES.findIndex(n => n.id === nodeId);

    if (status === 'completed') return 'completed';
    if (status === 'error' && nodeId === currentNode) return 'error';
    if (nodeId === currentNode) return 'active';
    if (nodeIndex < currentIndex) return 'completed';
    return 'pending';
  };

  const getStatusColor = (nodeStatus) => {
    switch (nodeStatus) {
      case 'completed': return '#10b981';
      case 'active': return '#3b82f6';
      case 'error': return '#ef4444';
      default: return '#d1d5db';
    }
  };

  return (
    <div className="workflow-visualization">
      <div
        className="workflow-header"
        onClick={() => setExpanded(!expanded)}
      >
        <h3>Workflow Status</h3>
        <div className="workflow-summary">
          <span className={`status-badge ${status}`}>{status}</span>
          <span className="expand-icon">{expanded ? '-' : '+'}</span>
        </div>
      </div>

      {/* Compact progress bar */}
      <div className="progress-bar">
        {WORKFLOW_NODES.filter(n => !n.optional).map((node, index) => (
          <React.Fragment key={node.id}>
            <div
              className={`progress-node ${getNodeStatus(node.id)}`}
              title={node.label}
            >
              <div
                className="node-dot"
                style={{ backgroundColor: getStatusColor(getNodeStatus(node.id)) }}
              />
            </div>
            {index < WORKFLOW_NODES.filter(n => !n.optional).length - 1 && (
              <div
                className="progress-line"
                style={{
                  backgroundColor: getNodeStatus(WORKFLOW_NODES[index + 1]?.id) === 'pending'
                    ? '#d1d5db'
                    : '#10b981'
                }}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Expanded view */}
      {expanded && (
        <div className="workflow-details">
          {loading ? (
            <div className="loading">Loading workflow details...</div>
          ) : (
            <>
              {/* Node timeline */}
              <div className="node-timeline">
                {WORKFLOW_NODES.map((node) => {
                  const nodeStatus = getNodeStatus(node.id);
                  const details = nodeDetails?.[node.id];

                  return (
                    <div
                      key={node.id}
                      className={`timeline-node ${nodeStatus} ${node.optional ? 'optional' : ''}`}
                    >
                      <div className="node-marker">
                        <div
                          className="marker-dot"
                          style={{ backgroundColor: getStatusColor(nodeStatus) }}
                        />
                        <div className="marker-line" />
                      </div>

                      <div className="node-content">
                        <div className="node-header">
                          <span className="node-label">{node.label}</span>
                          {node.optional && (
                            <span className="optional-badge">Optional</span>
                          )}
                        </div>

                        {details && (
                          <div className="node-details">
                            {details.startedAt && (
                              <span className="detail-time">
                                Started: {new Date(details.startedAt).toLocaleTimeString()}
                              </span>
                            )}
                            {details.completedAt && (
                              <span className="detail-time">
                                Completed: {new Date(details.completedAt).toLocaleTimeString()}
                              </span>
                            )}
                            {details.result && (
                              <div className="detail-result">
                                {typeof details.result === 'object' ? (
                                  <pre>{JSON.stringify(details.result, null, 2)}</pre>
                                ) : (
                                  <span>{details.result}</span>
                                )}
                              </div>
                            )}
                            {details.error && (
                              <div className="detail-error">
                                Error: {details.error}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Approval actions for human_gatekeeper node */}
                        {node.id === 'human_gatekeeper' && nodeStatus === 'active' && (
                          <div className="approval-actions">
                            <button
                              className="approve-btn"
                              onClick={() => onApprove?.(workflowId)}
                            >
                              Approve
                            </button>
                            <button
                              className="reject-btn"
                              onClick={() => onReject?.(workflowId)}
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Workflow metadata */}
              {nodeDetails?.metadata && (
                <div className="workflow-metadata">
                  <h4>Workflow Info</h4>
                  <div className="metadata-grid">
                    <div className="metadata-item">
                      <span className="label">Thread ID</span>
                      <span className="value">{nodeDetails.metadata.threadId}</span>
                    </div>
                    <div className="metadata-item">
                      <span className="label">Started</span>
                      <span className="value">
                        {new Date(nodeDetails.metadata.startedAt).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      <style jsx>{`
        .workflow-visualization {
          background: white;
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 16px;
          border: 1px solid #e5e7eb;
        }

        .workflow-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
        }

        .workflow-header h3 {
          margin: 0;
          font-size: 14px;
          color: #374151;
        }

        .workflow-summary {
          display: flex;
          align-items: center;
          gap: 12px;
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

        .status-badge.in_progress,
        .status-badge.awaiting_approval {
          background: #dbeafe;
          color: #2563eb;
        }

        .status-badge.error {
          background: #fee2e2;
          color: #dc2626;
        }

        .expand-icon {
          font-size: 18px;
          color: #6b7280;
          width: 24px;
          text-align: center;
        }

        .progress-bar {
          display: flex;
          align-items: center;
          margin-top: 16px;
          padding: 0 8px;
        }

        .progress-node {
          display: flex;
          align-items: center;
        }

        .node-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          transition: all 0.3s;
        }

        .progress-node.active .node-dot {
          box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
        }

        .progress-line {
          flex: 1;
          height: 3px;
          min-width: 20px;
          transition: background-color 0.3s;
        }

        .workflow-details {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid #f3f4f6;
        }

        .loading {
          text-align: center;
          color: #6b7280;
          padding: 20px;
        }

        .node-timeline {
          display: flex;
          flex-direction: column;
        }

        .timeline-node {
          display: flex;
          padding: 8px 0;
        }

        .timeline-node.optional {
          opacity: 0.7;
        }

        .node-marker {
          display: flex;
          flex-direction: column;
          align-items: center;
          margin-right: 12px;
        }

        .marker-dot {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          z-index: 1;
        }

        .marker-line {
          width: 2px;
          flex: 1;
          background: #e5e7eb;
          min-height: 20px;
        }

        .timeline-node:last-child .marker-line {
          display: none;
        }

        .node-content {
          flex: 1;
          padding-bottom: 12px;
        }

        .node-header {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .node-label {
          font-weight: 500;
          color: #374151;
        }

        .optional-badge {
          font-size: 10px;
          color: #9ca3af;
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .node-details {
          margin-top: 8px;
          font-size: 12px;
          color: #6b7280;
        }

        .detail-time {
          display: block;
          margin-bottom: 4px;
        }

        .detail-result {
          background: #f9fafb;
          padding: 8px;
          border-radius: 4px;
          margin-top: 8px;
          overflow-x: auto;
        }

        .detail-result pre {
          margin: 0;
          font-size: 11px;
          white-space: pre-wrap;
        }

        .detail-error {
          color: #dc2626;
          background: #fef2f2;
          padding: 8px;
          border-radius: 4px;
          margin-top: 8px;
        }

        .approval-actions {
          display: flex;
          gap: 8px;
          margin-top: 12px;
        }

        .approve-btn,
        .reject-btn {
          flex: 1;
          padding: 10px;
          border: none;
          border-radius: 6px;
          font-weight: 500;
          cursor: pointer;
        }

        .approve-btn {
          background: #10b981;
          color: white;
        }

        .reject-btn {
          background: #f3f4f6;
          color: #6b7280;
        }

        .workflow-metadata {
          margin-top: 16px;
          padding: 12px;
          background: #f9fafb;
          border-radius: 8px;
        }

        .workflow-metadata h4 {
          margin: 0 0 8px 0;
          font-size: 12px;
          color: #6b7280;
        }

        .metadata-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
        }

        .metadata-item {
          display: flex;
          flex-direction: column;
        }

        .metadata-item .label {
          font-size: 10px;
          color: #9ca3af;
        }

        .metadata-item .value {
          font-size: 12px;
          color: #374151;
          font-family: monospace;
        }
      `}</style>
    </div>
  );
};

export default WorkflowVisualization;
