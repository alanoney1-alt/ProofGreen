const PDFDocument = require('pdfkit');
const { format } = require('date-fns');
const { logger } = require('../utils/logger');

/**
 * Generate a PDF ESG report for a job
 */
async function generateJobReportPDF(job, company, items = []) {
  return new Promise((resolve, reject) => {
    try {
      const doc = new PDFDocument({
        size: 'A4',
        margin: 50,
        info: {
          Title: `ESG Report - ${job.job_number}`,
          Author: 'ProofGreen',
          Subject: 'Environmental Impact Report'
        }
      });

      const chunks = [];
      doc.on('data', chunk => chunks.push(chunk));
      doc.on('end', () => resolve(Buffer.concat(chunks)));
      doc.on('error', reject);

      // Colors
      const primaryColor = '#059669';
      const secondaryColor = '#0891B2';
      const textColor = '#1F2937';
      const mutedColor = '#6B7280';

      // Header with logo area
      doc
        .rect(0, 0, doc.page.width, 120)
        .fill(primaryColor);

      doc
        .fillColor('#FFFFFF')
        .fontSize(28)
        .font('Helvetica-Bold')
        .text('ProofGreen', 50, 40);

      doc
        .fontSize(12)
        .font('Helvetica')
        .text('Environmental Impact Report', 50, 75);

      // Company name in header
      doc
        .fontSize(14)
        .text(company.name, 50, 95, { align: 'left' });

      // Report date
      doc
        .fontSize(10)
        .text(format(new Date(), 'MMMM d, yyyy'), 450, 95, { align: 'right', width: 100 });

      // ESG Score badge
      const esgScore = job.esg_score || 0;
      const scoreColor = esgScore >= 80 ? '#059669' : esgScore >= 60 ? '#0891B2' : esgScore >= 40 ? '#F59E0B' : '#EF4444';

      doc
        .circle(520, 60, 35)
        .fill(scoreColor);

      doc
        .fillColor('#FFFFFF')
        .fontSize(24)
        .font('Helvetica-Bold')
        .text(esgScore.toString(), 495, 48, { width: 50, align: 'center' });

      doc
        .fontSize(8)
        .font('Helvetica')
        .text('ESG Score', 495, 72, { width: 50, align: 'center' });

      // Job Details Section
      let y = 150;

      doc
        .fillColor(textColor)
        .fontSize(18)
        .font('Helvetica-Bold')
        .text('Job Details', 50, y);

      y += 30;

      // Job info grid
      const jobDetails = [
        ['Job Number', job.job_number],
        ['Title', job.title || 'N/A'],
        ['Service Type', job.verticals?.name || 'General'],
        ['Status', job.status?.replace('_', ' ').toUpperCase()],
        ['Date', job.completed_at ? format(new Date(job.completed_at), 'MMM d, yyyy') : 'Pending']
      ];

      doc.fontSize(10).font('Helvetica');

      jobDetails.forEach(([label, value], index) => {
        const col = index % 2;
        const row = Math.floor(index / 2);
        const x = 50 + col * 250;
        const itemY = y + row * 25;

        doc.fillColor(mutedColor).text(label + ':', x, itemY);
        doc.fillColor(textColor).font('Helvetica-Bold').text(value, x + 80, itemY);
        doc.font('Helvetica');
      });

      y += Math.ceil(jobDetails.length / 2) * 25 + 30;

      // Key Metrics Section
      doc
        .fillColor(textColor)
        .fontSize(18)
        .font('Helvetica-Bold')
        .text('Environmental Impact Metrics', 50, y);

      y += 30;

      // Metrics boxes
      const metrics = [
        { label: 'Total Weight', value: `${(job.total_weight_lbs || 0).toLocaleString()} lbs`, color: '#6B7280' },
        { label: 'Recycled', value: `${(job.recycled_weight_lbs || 0).toLocaleString()} lbs`, color: '#059669' },
        { label: 'Donated', value: `${(job.donated_weight_lbs || 0).toLocaleString()} lbs`, color: '#0891B2' },
        { label: 'Landfill', value: `${(job.landfill_weight_lbs || 0).toLocaleString()} lbs`, color: '#6B7280' }
      ];

      const boxWidth = 115;
      const boxHeight = 60;
      const boxGap = 15;

      metrics.forEach((metric, index) => {
        const x = 50 + index * (boxWidth + boxGap);

        // Box background
        doc
          .rect(x, y, boxWidth, boxHeight)
          .fill('#F3F4F6');

        // Colored top border
        doc
          .rect(x, y, boxWidth, 4)
          .fill(metric.color);

        // Value
        doc
          .fillColor(textColor)
          .fontSize(16)
          .font('Helvetica-Bold')
          .text(metric.value, x + 10, y + 18, { width: boxWidth - 20, align: 'center' });

        // Label
        doc
          .fillColor(mutedColor)
          .fontSize(9)
          .font('Helvetica')
          .text(metric.label, x + 10, y + 40, { width: boxWidth - 20, align: 'center' });
      });

      y += boxHeight + 30;

      // Diversion Rate Progress Bar
      doc
        .fillColor(textColor)
        .fontSize(12)
        .font('Helvetica-Bold')
        .text('Diversion Rate', 50, y);

      const diversionRate = job.diversion_rate || 0;
      doc
        .fillColor(mutedColor)
        .fontSize(10)
        .font('Helvetica')
        .text(`${diversionRate.toFixed(1)}% of materials diverted from landfill`, 50, y + 15);

      y += 35;

      // Progress bar
      const barWidth = 495;
      const barHeight = 12;

      doc.rect(50, y, barWidth, barHeight).fill('#E5E7EB');
      doc.rect(50, y, barWidth * (diversionRate / 100), barHeight).fill(primaryColor);

      y += barHeight + 30;

      // Carbon Impact Section
      doc
        .fillColor(textColor)
        .fontSize(18)
        .font('Helvetica-Bold')
        .text('Carbon Impact', 50, y);

      y += 25;

      const carbonOffset = job.carbon_offset_lbs || 0;
      const treesEquivalent = Math.round(carbonOffset / 48); // ~48 lbs CO2 per tree per year
      const milesEquivalent = Math.round(carbonOffset / 0.89); // ~0.89 lbs CO2 per mile

      doc
        .fillColor(textColor)
        .fontSize(24)
        .font('Helvetica-Bold')
        .text(`${carbonOffset.toLocaleString()} lbs`, 50, y);

      doc
        .fillColor(mutedColor)
        .fontSize(12)
        .font('Helvetica')
        .text('CO2 emissions prevented', 50, y + 30);

      y += 60;

      // Environmental equivalents
      const equivalents = [
        { emoji: '🌳', value: treesEquivalent, label: 'Trees planted (annual equivalent)' },
        { emoji: '🚗', value: milesEquivalent.toLocaleString(), label: 'Car miles not driven' }
      ];

      equivalents.forEach((eq, index) => {
        const x = 50 + index * 250;
        doc.fontSize(20).text(eq.emoji, x, y);
        doc.fillColor(textColor).fontSize(14).font('Helvetica-Bold').text(eq.value.toString(), x + 30, y + 2);
        doc.fillColor(mutedColor).fontSize(9).font('Helvetica').text(eq.label, x + 30, y + 18);
      });

      y += 50;

      // Items Section (if present)
      if (items.length > 0) {
        // Check if we need a new page
        if (y > 650) {
          doc.addPage();
          y = 50;
        }

        doc
          .fillColor(textColor)
          .fontSize(18)
          .font('Helvetica-Bold')
          .text('Items Processed', 50, y);

        y += 25;

        // Table header
        doc
          .rect(50, y, 495, 25)
          .fill('#F3F4F6');

        doc
          .fillColor(textColor)
          .fontSize(9)
          .font('Helvetica-Bold')
          .text('Item', 60, y + 8)
          .text('Category', 200, y + 8)
          .text('Weight', 320, y + 8)
          .text('Disposition', 400, y + 8);

        y += 25;

        // Table rows
        items.slice(0, 15).forEach((item, index) => {
          const rowY = y + index * 22;

          if (index % 2 === 1) {
            doc.rect(50, rowY - 2, 495, 22).fill('#F9FAFB');
          }

          doc
            .fillColor(textColor)
            .fontSize(9)
            .font('Helvetica')
            .text(item.name?.substring(0, 25) || 'Unknown', 60, rowY + 4)
            .text(item.category || 'General', 200, rowY + 4)
            .text(`${item.weight_lbs || 0} lbs`, 320, rowY + 4)
            .text(item.disposal_method?.replace('_', ' ') || 'Pending', 400, rowY + 4);
        });

        if (items.length > 15) {
          y += 15 * 22 + 10;
          doc
            .fillColor(mutedColor)
            .fontSize(9)
            .text(`+ ${items.length - 15} more items`, 50, y);
        }
      }

      // Footer
      const footerY = doc.page.height - 60;

      doc
        .rect(0, footerY, doc.page.width, 60)
        .fill('#F3F4F6');

      doc
        .fillColor(mutedColor)
        .fontSize(8)
        .font('Helvetica')
        .text(
          'This report was generated by ProofGreen - AI-powered ESG tracking for home service businesses.',
          50,
          footerY + 15,
          { align: 'center', width: 495 }
        );

      doc
        .text(
          `Generated on ${format(new Date(), 'MMMM d, yyyy \'at\' h:mm a')}`,
          50,
          footerY + 30,
          { align: 'center', width: 495 }
        );

      doc.end();
    } catch (error) {
      logger.error('PDF generation error:', error);
      reject(error);
    }
  });
}

/**
 * Generate a summary report PDF for a period
 */
async function generatePeriodReportPDF(company, metrics, period) {
  return new Promise((resolve, reject) => {
    try {
      const doc = new PDFDocument({
        size: 'A4',
        margin: 50,
        info: {
          Title: `ESG Summary Report - ${company.name}`,
          Author: 'ProofGreen',
          Subject: 'Environmental Impact Summary Report'
        }
      });

      const chunks = [];
      doc.on('data', chunk => chunks.push(chunk));
      doc.on('end', () => resolve(Buffer.concat(chunks)));
      doc.on('error', reject);

      // Colors
      const primaryColor = '#059669';
      const textColor = '#1F2937';
      const mutedColor = '#6B7280';

      // Header
      doc
        .rect(0, 0, doc.page.width, 120)
        .fill(primaryColor);

      doc
        .fillColor('#FFFFFF')
        .fontSize(28)
        .font('Helvetica-Bold')
        .text('ProofGreen', 50, 40);

      doc
        .fontSize(14)
        .font('Helvetica')
        .text(`${period.label} Summary Report`, 50, 75);

      doc
        .fontSize(12)
        .text(company.name, 50, 95);

      // Period dates
      doc
        .fontSize(10)
        .text(
          `${format(new Date(period.start), 'MMM d, yyyy')} - ${format(new Date(period.end), 'MMM d, yyyy')}`,
          400,
          95,
          { align: 'right', width: 145 }
        );

      let y = 150;

      // Summary stats
      doc
        .fillColor(textColor)
        .fontSize(18)
        .font('Helvetica-Bold')
        .text('Summary', 50, y);

      y += 30;

      const summaryStats = [
        { label: 'Total Jobs', value: metrics.totalJobs || 0 },
        { label: 'Total Weight', value: `${(metrics.totalWeight || 0).toLocaleString()} lbs` },
        { label: 'Diverted', value: `${((metrics.recycledWeight || 0) + (metrics.donatedWeight || 0)).toLocaleString()} lbs` },
        { label: 'Carbon Offset', value: `${(metrics.carbonOffset || 0).toLocaleString()} lbs CO2` },
        { label: 'Avg ESG Score', value: metrics.averageEsgScore || 0 },
        { label: 'Diversion Rate', value: `${(metrics.diversionRate || 0).toFixed(1)}%` }
      ];

      const boxWidth = 150;
      const boxHeight = 70;

      summaryStats.forEach((stat, index) => {
        const col = index % 3;
        const row = Math.floor(index / 3);
        const x = 50 + col * (boxWidth + 20);
        const boxY = y + row * (boxHeight + 15);

        doc.rect(x, boxY, boxWidth, boxHeight).fill('#F3F4F6');

        doc
          .fillColor(textColor)
          .fontSize(20)
          .font('Helvetica-Bold')
          .text(stat.value.toString(), x + 10, boxY + 15, { width: boxWidth - 20, align: 'center' });

        doc
          .fillColor(mutedColor)
          .fontSize(10)
          .font('Helvetica')
          .text(stat.label, x + 10, boxY + 45, { width: boxWidth - 20, align: 'center' });
      });

      y += Math.ceil(summaryStats.length / 3) * (boxHeight + 15) + 30;

      // Environmental Impact
      doc
        .fillColor(textColor)
        .fontSize(18)
        .font('Helvetica-Bold')
        .text('Environmental Impact', 50, y);

      y += 30;

      const carbonOffset = metrics.carbonOffset || 0;
      const treesEquivalent = Math.round(carbonOffset / 48);
      const milesEquivalent = Math.round(carbonOffset / 0.89);
      const tonsFromLandfill = ((metrics.recycledWeight || 0) + (metrics.donatedWeight || 0)) / 2000;

      doc
        .fontSize(12)
        .font('Helvetica')
        .fillColor(textColor)
        .text(`By diverting ${tonsFromLandfill.toFixed(2)} tons of material from landfills, ${company.name} has made a significant environmental impact:`, 50, y, { width: 495 });

      y += 40;

      const impacts = [
        { value: `${carbonOffset.toLocaleString()} lbs`, label: 'CO2 emissions prevented' },
        { value: treesEquivalent.toString(), label: 'Trees planted (equivalent)' },
        { value: milesEquivalent.toLocaleString(), label: 'Car miles offset' }
      ];

      impacts.forEach((impact, index) => {
        const x = 50 + index * 170;
        doc
          .fillColor(primaryColor)
          .fontSize(24)
          .font('Helvetica-Bold')
          .text(impact.value, x, y);

        doc
          .fillColor(mutedColor)
          .fontSize(10)
          .font('Helvetica')
          .text(impact.label, x, y + 28);
      });

      // Footer
      const footerY = doc.page.height - 60;

      doc
        .rect(0, footerY, doc.page.width, 60)
        .fill('#F3F4F6');

      doc
        .fillColor(mutedColor)
        .fontSize(8)
        .font('Helvetica')
        .text(
          'This report was generated by ProofGreen - AI-powered ESG tracking for home service businesses.',
          50,
          footerY + 15,
          { align: 'center', width: 495 }
        );

      doc
        .text(
          `Generated on ${format(new Date(), 'MMMM d, yyyy \'at\' h:mm a')}`,
          50,
          footerY + 30,
          { align: 'center', width: 495 }
        );

      doc.end();
    } catch (error) {
      logger.error('Period report PDF generation error:', error);
      reject(error);
    }
  });
}

module.exports = {
  generateJobReportPDF,
  generatePeriodReportPDF
};
