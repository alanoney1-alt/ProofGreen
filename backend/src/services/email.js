const nodemailer = require('nodemailer');
const { logger } = require('../utils/logger');

// Create transporter
const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST || 'smtp.resend.com',
  port: parseInt(process.env.SMTP_PORT) || 587,
  secure: process.env.SMTP_SECURE === 'true',
  auth: {
    user: process.env.SMTP_USER || 'resend',
    pass: process.env.SMTP_PASS || process.env.RESEND_API_KEY
  }
});

const FROM_EMAIL = process.env.FROM_EMAIL || 'ProofGreen <noreply@proofgreen.com>';
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5173';

/**
 * Send email using template
 */
async function sendEmail(to, subject, html, text = null) {
  try {
    const info = await transporter.sendMail({
      from: FROM_EMAIL,
      to,
      subject,
      html,
      text: text || html.replace(/<[^>]*>/g, '')
    });

    logger.info(`Email sent to ${to}: ${info.messageId}`);
    return info;
  } catch (error) {
    logger.error('Failed to send email:', error);
    throw error;
  }
}

/**
 * Welcome email for new users
 */
async function sendWelcomeEmail(user, company) {
  const subject = `Welcome to ProofGreen, ${user.first_name}!`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #059669, #0891b2); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { color: white; margin: 0; font-size: 28px; }
        .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }
        .button { display: inline-block; background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }
        .feature { padding: 15px; background: #f3f4f6; border-radius: 6px; margin: 10px 0; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>🌱 Welcome to ProofGreen!</h1>
        </div>
        <div class="content">
          <p>Hi ${user.first_name},</p>
          <p>Thank you for signing up <strong>${company.name}</strong> with ProofGreen! You're now ready to start tracking your environmental impact and proving your sustainability efforts.</p>

          <h3>Here's what you can do next:</h3>

          <div class="feature">
            <strong>📸 Upload job photos</strong><br>
            Our AI will automatically identify items and calculate your environmental impact.
          </div>

          <div class="feature">
            <strong>📊 Track your metrics</strong><br>
            See your diversion rates, carbon offset, and ESG scores in real-time.
          </div>

          <div class="feature">
            <strong>📄 Generate reports</strong><br>
            Create professional ESG reports to share with customers and stakeholders.
          </div>

          <div class="feature">
            <strong>🏆 Earn milestones</strong><br>
            Track your progress and celebrate your environmental achievements.
          </div>

          <p style="text-align: center; margin-top: 30px;">
            <a href="${FRONTEND_URL}" class="button">Get Started</a>
          </p>

          <p>If you have any questions, just reply to this email - we're here to help!</p>

          <p>Best regards,<br>The ProofGreen Team</p>
        </div>
        <div class="footer">
          <p>ProofGreen - AI-powered ESG tracking for home service businesses</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return sendEmail(user.email, subject, html);
}

/**
 * Milestone achievement notification
 */
async function sendMilestoneEmail(user, company, milestone) {
  const subject = `🏆 Congratulations! You've earned a new milestone`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #f59e0b, #f97316); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { color: white; margin: 0; font-size: 28px; }
        .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }
        .milestone-badge { text-align: center; padding: 30px; background: #fef3c7; border-radius: 8px; margin: 20px 0; }
        .milestone-badge .icon { font-size: 48px; margin-bottom: 10px; }
        .milestone-badge h2 { color: #d97706; margin: 0; }
        .button { display: inline-block; background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>🏆 New Milestone Achieved!</h1>
        </div>
        <div class="content">
          <p>Hi ${user.first_name},</p>
          <p>Amazing news! <strong>${company.name}</strong> has just earned a new environmental milestone:</p>

          <div class="milestone-badge">
            <div class="icon">🏆</div>
            <h2>${milestone.name}</h2>
            <p style="color: #92400e; margin: 10px 0 0;">${milestone.description}</p>
          </div>

          <p>This achievement reflects your commitment to sustainability and environmental responsibility. Keep up the great work!</p>

          <p style="text-align: center; margin-top: 30px;">
            <a href="${FRONTEND_URL}" class="button">View Your Progress</a>
          </p>

          <p>Best regards,<br>The ProofGreen Team</p>
        </div>
        <div class="footer">
          <p>ProofGreen - AI-powered ESG tracking for home service businesses</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return sendEmail(user.email, subject, html);
}

/**
 * Job completed notification with ESG summary
 */
async function sendJobCompletedEmail(user, company, job) {
  const subject = `Job ${job.job_number} completed - ESG Score: ${job.esg_score}`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #059669, #0891b2); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { color: white; margin: 0; font-size: 24px; }
        .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }
        .metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }
        .metric { padding: 15px; background: #f3f4f6; border-radius: 6px; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #059669; }
        .metric-label { font-size: 12px; color: #6b7280; }
        .esg-score { text-align: center; padding: 20px; background: linear-gradient(135deg, #059669, #0891b2); border-radius: 8px; color: white; margin: 20px 0; }
        .esg-score .value { font-size: 48px; font-weight: bold; }
        .button { display: inline-block; background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Job Completed: ${job.job_number}</h1>
        </div>
        <div class="content">
          <p>Hi ${user.first_name},</p>
          <p>Great news! Job <strong>${job.job_number}</strong> (${job.title || 'Untitled'}) has been completed and processed by our AI.</p>

          <div class="esg-score">
            <div class="value">${job.esg_score || 0}</div>
            <div>ESG Score</div>
          </div>

          <div class="metrics-grid">
            <div class="metric">
              <div class="metric-value">${(job.total_weight_lbs || 0).toLocaleString()}</div>
              <div class="metric-label">Total Weight (lbs)</div>
            </div>
            <div class="metric">
              <div class="metric-value">${(job.diversion_rate || 0).toFixed(1)}%</div>
              <div class="metric-label">Diversion Rate</div>
            </div>
            <div class="metric">
              <div class="metric-value">${(job.recycled_weight_lbs || 0).toLocaleString()}</div>
              <div class="metric-label">Recycled (lbs)</div>
            </div>
            <div class="metric">
              <div class="metric-value">${(job.carbon_offset_lbs || 0).toLocaleString()}</div>
              <div class="metric-label">CO2 Offset (lbs)</div>
            </div>
          </div>

          <p style="text-align: center; margin-top: 30px;">
            <a href="${FRONTEND_URL}/jobs/${job.id}" class="button">View Full Report</a>
          </p>

          <p>Best regards,<br>The ProofGreen Team</p>
        </div>
        <div class="footer">
          <p>ProofGreen - AI-powered ESG tracking for home service businesses</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return sendEmail(user.email, subject, html);
}

/**
 * Weekly summary email
 */
async function sendWeeklySummaryEmail(user, company, metrics) {
  const subject = `Your weekly ESG summary - ${company.name}`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #059669, #0891b2); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { color: white; margin: 0; font-size: 24px; }
        .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }
        .stats-row { display: flex; justify-content: space-between; margin: 20px 0; }
        .stat { text-align: center; flex: 1; }
        .stat-value { font-size: 28px; font-weight: bold; color: #059669; }
        .stat-label { font-size: 12px; color: #6b7280; }
        .highlight { background: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #059669; }
        .button { display: inline-block; background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>📊 Weekly ESG Summary</h1>
        </div>
        <div class="content">
          <p>Hi ${user.first_name},</p>
          <p>Here's your environmental impact summary for the past week:</p>

          <div class="stats-row">
            <div class="stat">
              <div class="stat-value">${metrics.jobsCompleted || 0}</div>
              <div class="stat-label">Jobs Completed</div>
            </div>
            <div class="stat">
              <div class="stat-value">${((metrics.totalWeight || 0) / 2000).toFixed(2)}</div>
              <div class="stat-label">Tons Processed</div>
            </div>
            <div class="stat">
              <div class="stat-value">${(metrics.diversionRate || 0).toFixed(0)}%</div>
              <div class="stat-label">Diversion Rate</div>
            </div>
          </div>

          <div class="highlight">
            <strong>🌱 Environmental Impact</strong><br>
            This week, ${company.name} prevented <strong>${(metrics.carbonOffset || 0).toLocaleString()} lbs</strong> of CO2 emissions - equivalent to planting <strong>${Math.round((metrics.carbonOffset || 0) / 48)} trees</strong>!
          </div>

          <p style="text-align: center; margin-top: 30px;">
            <a href="${FRONTEND_URL}/metrics" class="button">View Full Dashboard</a>
          </p>

          <p>Keep up the great work!</p>

          <p>Best regards,<br>The ProofGreen Team</p>
        </div>
        <div class="footer">
          <p>ProofGreen - AI-powered ESG tracking for home service businesses</p>
          <p style="font-size: 12px;">You're receiving this because you're subscribed to weekly summaries. <a href="${FRONTEND_URL}/settings">Manage preferences</a></p>
        </div>
      </div>
    </body>
    </html>
  `;

  return sendEmail(user.email, subject, html);
}

/**
 * Team invitation email
 */
async function sendTeamInviteEmail(inviterName, companyName, inviteEmail, inviteToken) {
  const subject = `${inviterName} invited you to join ${companyName} on ProofGreen`;

  const inviteUrl = `${FRONTEND_URL}/invite/${inviteToken}`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #059669, #0891b2); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { color: white; margin: 0; font-size: 24px; }
        .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; text-align: center; }
        .button { display: inline-block; background: #059669; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>🌱 You're Invited!</h1>
        </div>
        <div class="content">
          <p><strong>${inviterName}</strong> has invited you to join <strong>${companyName}</strong> on ProofGreen.</p>

          <p>ProofGreen helps home service businesses track their environmental impact with AI-powered ESG analytics.</p>

          <p style="margin: 30px 0;">
            <a href="${inviteUrl}" class="button">Accept Invitation</a>
          </p>

          <p style="color: #6b7280; font-size: 14px;">This invitation will expire in 7 days.</p>
        </div>
        <div class="footer">
          <p>ProofGreen - AI-powered ESG tracking for home service businesses</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return sendEmail(inviteEmail, subject, html);
}

/**
 * Password reset email
 */
async function sendPasswordResetEmail(user, resetToken) {
  const subject = 'Reset your ProofGreen password';

  const resetUrl = `${FRONTEND_URL}/reset-password/${resetToken}`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #f3f4f6; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { color: #1f2937; margin: 0; font-size: 24px; }
        .content { background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; }
        .button { display: inline-block; background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 600; }
        .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }
        .warning { background: #fef3c7; padding: 15px; border-radius: 6px; margin: 20px 0; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>🔐 Password Reset</h1>
        </div>
        <div class="content">
          <p>Hi ${user.first_name},</p>
          <p>We received a request to reset your password. Click the button below to choose a new password:</p>

          <p style="text-align: center; margin: 30px 0;">
            <a href="${resetUrl}" class="button">Reset Password</a>
          </p>

          <div class="warning">
            <strong>⚠️ Security Notice:</strong> This link will expire in 1 hour. If you didn't request this reset, you can safely ignore this email.
          </div>

          <p>Best regards,<br>The ProofGreen Team</p>
        </div>
        <div class="footer">
          <p>ProofGreen - AI-powered ESG tracking for home service businesses</p>
        </div>
      </div>
    </body>
    </html>
  `;

  return sendEmail(user.email, subject, html);
}

module.exports = {
  sendEmail,
  sendWelcomeEmail,
  sendMilestoneEmail,
  sendJobCompletedEmail,
  sendWeeklySummaryEmail,
  sendTeamInviteEmail,
  sendPasswordResetEmail
};
