"""
Reports Routes - PDF/Excel report generation (paid feature)
"""
import os
import json
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from database import db, User, ExcelFile, Analysis, Report

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate_report():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    data = request.get_json()
    
    file_id = data.get('file_id')
    analysis_id = data.get('analysis_id')
    report_type = data.get('report_type', 'pdf')  # pdf, excel, dashboard
    title = data.get('title', 'Analysis Report')
    
    # Every report download consumes 1 credit, regardless of plan
    if user.download_credits <= 0:
        return jsonify({
            'error': 'You have no download credits remaining. Please upgrade your plan or buy more credits.',
            'upgrade_required': True,
            'credits_remaining': user.download_credits,
        }), 403
    
    excel_file = ExcelFile.query.filter_by(id=file_id, user_id=user.id).first()
    if not excel_file:
        return jsonify({'error': 'File not found'}), 404
    
    analysis = None
    if analysis_id:
        analysis = Analysis.query.filter_by(id=analysis_id, user_id=user.id).first()
    
    try:
        if report_type == 'pdf':
            report_path = generate_pdf_report(excel_file, analysis, title, current_app.config['REPORTS_FOLDER'])
        elif report_type == 'excel':
            report_path = generate_excel_report(excel_file, analysis, title, current_app.config['REPORTS_FOLDER'])
        else:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Deduct 1 credit for every successful report download (all plans)
        user.download_credits = max(0, user.download_credits - 1)
        
        # Save report record
        report = Report(
            user_id=user.id,
            file_id=file_id,
            analysis_id=analysis_id,
            title=title,
            report_type=report_type,
            file_path=report_path,
            is_paid=True,
            price=0.0
        )
        db.session.add(report)
        db.session.commit()
        
        return jsonify({
            'message': 'Report generated successfully',
            'report_id': report.id,
            'download_url': f'/api/reports/{report.id}/download',
            'credits_remaining': user.download_credits
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_pdf_report(excel_file, analysis, title, reports_folder):
    """Generate a PDF report using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import uuid
    
    filename = f"report_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(reports_folder, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=A4, 
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
                                  fontSize=24, textColor=colors.HexColor('#1a1a2e'))
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # File info
    story.append(Paragraph(f"<b>File:</b> {excel_file.original_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Rows:</b> {excel_file.total_rows} | <b>Columns:</b> {excel_file.total_cols}", styles['Normal']))
    story.append(Paragraph(f"<b>Data Quality Score:</b> {excel_file.data_quality_score}/100", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Summary table
    insights = json.loads(excel_file.file_insights or '{}')
    summary = insights.get('summary', {})
    
    table_data = [
        ['Metric', 'Value'],
        ['Total Rows', str(excel_file.total_rows)],
        ['Total Columns', str(excel_file.total_cols)],
        ['Missing Values', str(excel_file.missing_values)],
        ['Duplicate Rows', str(excel_file.duplicate_rows)],
        ['Quality Score', f"{excel_file.data_quality_score}/100"],
        ['Numeric Columns', str(summary.get('numeric_cols_count', 0))],
        ['Text Columns', str(summary.get('text_cols_count', 0))],
        ['Date Columns', str(summary.get('date_cols_count', 0))],
    ]
    
    table = Table(table_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*inch))
    
    # Analysis results
    if analysis and analysis.ai_narrative:
        story.append(Paragraph('<b>AI Analysis Narrative</b>', styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        for line in analysis.ai_narrative.split('\n'):
            if line.strip():
                story.append(Paragraph(line, styles['Normal']))
                story.append(Spacer(1, 0.05*inch))
    
    # Warnings
    warnings = insights.get('warnings', [])
    if warnings:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph('<b>Data Warnings</b>', styles['Heading2']))
        for w in warnings:
            story.append(Paragraph(f"• {w}", styles['Normal']))
    
    doc.build(story)
    return filepath


def generate_excel_report(excel_file, analysis, title, reports_folder):
    """Generate an Excel report."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    import uuid
    
    filename = f"report_{uuid.uuid4().hex[:8]}.xlsx"
    filepath = os.path.join(reports_folder, filename)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    
    # Header
    ws['A1'] = title
    ws['A1'].font = Font(size=20, bold=True, color='1a1a2e')
    ws['A2'] = f"Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws.merge_cells('A1:F1')
    ws.merge_cells('A2:F2')
    
    # File info table
    headers = ['Metric', 'Value']
    data = [
        ['File Name', excel_file.original_name],
        ['Total Rows', excel_file.total_rows],
        ['Total Columns', excel_file.total_cols],
        ['Total Cells', excel_file.total_cells],
        ['Missing Values', excel_file.missing_values],
        ['Duplicate Rows', excel_file.duplicate_rows],
        ['Data Quality Score', f"{excel_file.data_quality_score}/100"],
        ['File Type', excel_file.file_type.upper()],
    ]
    
    start_row = 4
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=ci, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='1a1a2e', end_color='1a1a2e', fill_type='solid')
        cell.alignment = Alignment(horizontal='center')
    
    for ri, row in enumerate(data, start_row + 1):
        for ci, val in enumerate(row, 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            if ri % 2 == 0:
                cell.fill = PatternFill(start_color='f8f9fa', end_color='f8f9fa', fill_type='solid')
    
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 35
    
    wb.save(filepath)
    return filepath


@reports_bp.route('/<int:report_id>/download', methods=['GET'])
@jwt_required()
def download_report(report_id):
    identity = get_jwt_identity()
    report = Report.query.filter_by(id=report_id, user_id=int(identity)).first()
    
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    
    if not os.path.exists(report.file_path):
        return jsonify({'error': 'Report file not found'}), 404
    
    mime_types = {'pdf': 'application/pdf', 'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    mime = mime_types.get(report.report_type, 'application/octet-stream')
    ext = 'pdf' if report.report_type == 'pdf' else 'xlsx'
    
    return send_file(
        report.file_path,
        mimetype=mime,
        as_attachment=True,
        download_name=f"{report.title.replace(' ', '_')}.{ext}"
    )


@reports_bp.route('/list', methods=['GET'])
@jwt_required()
def list_reports():
    identity = get_jwt_identity()
    reports = Report.query.filter_by(user_id=int(identity))\
        .order_by(Report.created_at.desc()).all()
    return jsonify({'reports': [r.to_dict() for r in reports]}), 200