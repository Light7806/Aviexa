"""
reports/pdf_generator.py
Premium PDF report generator for Aviexa sessions.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime
import logging
import json
import xml.sax.saxutils as saxutils

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether, HRFlowable, Preformatted
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from reports.chart_builder import ChartBuilder

logger = logging.getLogger(__name__)


def _esc(value) -> str:
    """Safely escape any value for ReportLab XML Paragraph rendering."""
    return saxutils.escape(str(value)) if value is not None else ""


# ── Colour palette ────────────────────────────────────────────────────────────
C_PRIMARY   = colors.HexColor('#0e639c')
C_DARK      = colors.HexColor('#1e1e1e')
C_MEDIUM    = colors.HexColor('#2c3e50')
C_LIGHT_BG  = colors.HexColor('#f8f9fa')
C_BORDER    = colors.HexColor('#dddddd')
C_WHITE     = colors.white
C_DANGER    = colors.HexColor('#c0392b')
C_SUCCESS   = colors.HexColor('#27ae60')
C_MUTED     = colors.HexColor('#555555')
C_CODE_BG   = colors.HexColor('#1e1e1e')
C_CODE_TEXT = colors.HexColor('#d4d4d4')


class AviexaPDFReportGenerator:
    """
    Generates premium hackathon-ready PDF reports for Aviexa sessions.
    Features full escaping, table-based layouts, and numbered IBM Bob section.
    """

    def __init__(self, pagesize=letter):
        self.pagesize = pagesize
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.chart_builder = ChartBuilder()

    # ── Style setup ───────────────────────────────────────────────────────────

    def _setup_styles(self):
        s = self.styles

        def add(name, parent='Normal', **kw):
            s.add(ParagraphStyle(name=name, parent=s[parent], **kw))

        add('AvTitle',    parent='Normal', fontSize=32, textColor=C_PRIMARY,
            alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=8)
        add('AvSubtitle', parent='Normal', fontSize=13, textColor=C_MUTED,
            alignment=TA_CENTER, fontName='Helvetica', spaceAfter=6)
        add('AvBadge',    parent='Normal', fontSize=11, textColor=C_WHITE,
            alignment=TA_CENTER, fontName='Helvetica-Bold', spaceAfter=30,
            backColor=C_PRIMARY, borderPadding=6)
        add('AvSection',  parent='Heading2', fontSize=16, textColor=C_DARK,
            fontName='Helvetica-Bold', spaceBefore=22, spaceAfter=10)
        add('AvBody',     parent='Normal', fontSize=10, textColor=C_DARK,
            fontName='Helvetica', spaceAfter=6, leading=14)
        add('AvBold',     parent='Normal', fontSize=10, textColor=C_DARK,
            fontName='Helvetica-Bold', spaceAfter=4)
        add('AvMuted',    parent='Normal', fontSize=9, textColor=C_MUTED,
            fontName='Helvetica', spaceAfter=4)
        add('AvCode',     parent='Normal', fontSize=8, textColor=C_CODE_TEXT,
            fontName='Courier', backColor=C_CODE_BG,
            leftIndent=8, rightIndent=8, borderPadding=6, spaceAfter=8)
        add('AvNumbered', parent='Normal', fontSize=10, textColor=C_DARK,
            fontName='Helvetica', leftIndent=16, spaceAfter=5, leading=14)

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(self, session_record, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            output_dir = Path("aviexa-reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"aviexa_report_{session_record.session_id[:8]}_{ts}.pdf"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path), pagesize=self.pagesize,
            rightMargin=60, leftMargin=60, topMargin=60, bottomMargin=40
        )

        story = []
        story.extend(self._cover(session_record));           story.append(PageBreak())
        story.extend(self._executive_summary(session_record)); story.append(Spacer(1, 0.25*inch))
        if session_record.anomalies:
            story.extend(self._anomaly_timeline(session_record)); story.append(Spacer(1, 0.2*inch))
        charts = self._charts_section(session_record)
        if charts:
            story.extend(charts); story.append(PageBreak())
        if session_record.diagnoses:
            story.extend(self._diagnoses_section(session_record)); story.append(PageBreak())
            story.extend(self._suggested_fixes_section(session_record)); story.append(Spacer(1, 0.2*inch))
        story.extend(self._applied_fixes_section(session_record)); story.append(Spacer(1, 0.2*inch))
        story.extend(self._bob_usage_section()); story.append(PageBreak())
        story.extend(self._appendix(session_record))

        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return output_path

    # ── Cover page ────────────────────────────────────────────────────────────

    def _cover(self, sr) -> list:
        story = [Spacer(1, 1.5*inch)]
        story.append(Paragraph("Aviexa", self.styles['AvTitle']))
        story.append(Paragraph(
            "Real-time ML training diagnostics with AI-generated root cause analysis.",
            self.styles['AvSubtitle']))
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph("Powered by IBM Bob", self.styles['AvBadge']))
        story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER))
        story.append(Spacer(1, 0.4*inch))

        info = [
            ['Session ID',   _esc(sr.session_id)],
            ['Status',       _esc(sr.status.value)],
            ['Created',      sr.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')],
            ['Script',       _esc(sr.script_path or 'N/A')],
            ['Generated',    datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ]
        t = Table(info, colWidths=[1.6*inch, 4.4*inch])
        t.setStyle(TableStyle([
            ('FONTNAME',  (0,0),(0,-1), 'Helvetica-Bold'),
            ('FONTNAME',  (1,0),(1,-1), 'Helvetica'),
            ('FONTSIZE',  (0,0),(-1,-1), 10),
            ('TEXTCOLOR', (0,0),(0,-1), C_PRIMARY),
            ('BOTTOMPADDING',(0,0),(-1,-1), 7),
            ('TOPPADDING',   (0,0),(-1,-1), 7),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[C_LIGHT_BG, C_WHITE]),
            ('GRID',     (0,0),(-1,-1), 0.5, C_BORDER),
        ]))
        story.append(t)
        return story

    # ── Executive summary ─────────────────────────────────────────────────────

    def _executive_summary(self, sr) -> list:
        story = [Paragraph("Executive Summary", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_PRIMARY))
        story.append(Spacer(1, 0.1*inch))

        n_fixes = sum(len(d.fixes) for d in sr.diagnoses)
        rows = [
            ['Metric', 'Count', 'Status'],
            ['Total Telemetry Events',   str(len(sr.telemetry_events)), '-'],
            ['Anomalies Detected',        str(len(sr.anomalies)),
             'ALERT' if sr.anomalies else 'OK'],
            ['Bob Diagnoses Generated',   str(len(sr.diagnoses)),
             'OK' if sr.diagnoses else '-'],
            ['Fixes Suggested',           str(n_fixes),
             'OK' if n_fixes else '-'],
            ['Fixes Applied',             str(len(sr.applied_fixes)),
             'APPLIED' if sr.applied_fixes else '-'],
        ]
        t = Table(rows, colWidths=[3*inch, 1.2*inch, 1.8*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0), C_PRIMARY),
            ('TEXTCOLOR',     (0,0),(-1,0), C_WHITE),
            ('FONTNAME',      (0,0),(-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0),(-1,-1), 10),
            ('ALIGN',         (1,0),(-1,-1), 'CENTER'),
            ('TOPPADDING',    (0,0),(-1,-1), 9),
            ('BOTTOMPADDING', (0,0),(-1,-1), 9),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_LIGHT_BG, C_WHITE]),
            ('GRID',          (0,0),(-1,-1), 0.5, C_BORDER),
            # Highlight anomaly row red if anomalies found
            *([('TEXTCOLOR', (2,2),(2,2), C_DANGER),
               ('FONTNAME',  (2,2),(2,2), 'Helvetica-Bold')]
              if sr.anomalies else []),
            # Highlight applied fixes green
            *([('TEXTCOLOR', (2,5),(2,5), C_SUCCESS),
               ('FONTNAME',  (2,5),(2,5), 'Helvetica-Bold')]
              if sr.applied_fixes else []),
        ]))
        story.append(t)
        return story

    # ── Anomaly timeline ──────────────────────────────────────────────────────

    def _anomaly_timeline(self, sr) -> list:
        story = [Paragraph("Anomaly Timeline", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_DANGER))
        story.append(Spacer(1, 0.1*inch))

        header = [['#', 'Step', 'Type', 'Layer', 'Conf.', 'Description']]
        rows = []
        for i, a in enumerate(sr.anomalies[:15], 1):
            atype = a.anomaly_type.value if hasattr(a.anomaly_type, 'value') else str(a.anomaly_type)
            desc = (a.description or '')[:90]
            rows.append([
                str(i),
                str(a.step),
                _esc(atype.replace('_', ' ').title()),
                _esc(a.layer_name or 'N/A'),
                f"{a.confidence:.0%}",
                Paragraph(_esc(desc), self.styles['AvMuted']),
            ])

        t = Table(header + rows, colWidths=[0.3*inch, 0.5*inch, 1.3*inch, 1.0*inch, 0.55*inch, 2.85*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,0), C_DANGER),
            ('TEXTCOLOR',     (0,0),(-1,0), C_WHITE),
            ('FONTNAME',      (0,0),(-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0),(-1,-1), 9),
            ('TOPPADDING',    (0,0),(-1,-1), 7),
            ('BOTTOMPADDING', (0,0),(-1,-1), 7),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_LIGHT_BG, C_WHITE]),
            ('GRID',          (0,0),(-1,-1), 0.5, C_BORDER),
            ('FONTNAME',      (4,1),(4,-1), 'Helvetica-Bold'),
            ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ]))
        story.append(t)

        if len(sr.anomalies) > 15:
            story.append(Paragraph(
                f"<i>...and {len(sr.anomalies)-15} more anomalies not shown.</i>",
                self.styles['AvMuted']))
        return story

    # ── Charts ────────────────────────────────────────────────────────────────

    def _charts_section(self, sr) -> list:
        charts_dir = Path("aviexa-reports") / "charts" / sr.session_id[:8]
        charts_dir.mkdir(parents=True, exist_ok=True)
        charts = self.chart_builder.build_all_charts(sr, charts_dir)

        if not any(charts.values()):
            return []

        story = [Paragraph("Training Metrics", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_PRIMARY))
        story.append(Spacer(1, 0.1*inch))

        for label, path in charts.items():
            if path and path.exists():
                try:
                    story.append(Image(str(path), width=6*inch, height=3.5*inch))
                    story.append(Spacer(1, 0.15*inch))
                except Exception as e:
                    logger.warning(f"Could not embed {label} chart: {e}")
        return story

    # ── Diagnoses ─────────────────────────────────────────────────────────────

    def _diagnoses_section(self, sr) -> list:
        story = [Paragraph("IBM Bob Diagnoses", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_PRIMARY))
        story.append(Spacer(1, 0.1*inch))

        for i, diag in enumerate(sr.diagnoses, 1):
            block = []
            block.append(Paragraph(f"<b>Diagnosis {i}</b>", self.styles['AvBold']))
            block.append(Paragraph(_esc(diag.summary), self.styles['AvBody']))
            block.append(Spacer(1, 0.08*inch))

            if diag.hypotheses:
                hyp_rows = [['Hypothesis', 'Confidence', 'Evidence']]
                for h in diag.hypotheses:
                    ev = '; '.join(_esc(e) for e in (h.evidence or [])[:2])
                    hyp_rows.append([
                        _esc(h.title),
                        f"{h.confidence:.0%}",
                        ev or '-',
                    ])
                ht = Table(hyp_rows, colWidths=[2.2*inch, 1*inch, 2.8*inch])
                ht.setStyle(TableStyle([
                    ('BACKGROUND',    (0,0),(-1,0), C_MEDIUM),
                    ('TEXTCOLOR',     (0,0),(-1,0), C_WHITE),
                    ('FONTNAME',      (0,0),(-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE',      (0,0),(-1,-1), 9),
                    ('TOPPADDING',    (0,0),(-1,-1), 6),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 6),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_LIGHT_BG, C_WHITE]),
                    ('GRID',          (0,0),(-1,-1), 0.5, C_BORDER),
                ]))
                block.append(ht)

            story.append(KeepTogether(block))
            story.append(Spacer(1, 0.2*inch))

        return story

    # ── Suggested fixes ───────────────────────────────────────────────────────

    def _suggested_fixes_section(self, sr) -> list:
        story = [Paragraph("Suggested Fixes", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_SUCCESS))
        story.append(Spacer(1, 0.1*inch))

        n = 0
        for diag in sr.diagnoses:
            for fix in diag.fixes:
                n += 1
                block = []
                block.append(Paragraph(
                    f"<b>Fix {n}:</b> {_esc(fix.file_path)} "
                    f"(lines {fix.start_line}-{fix.end_line})",
                    self.styles['AvBold']))
                block.append(Paragraph(
                    f"<b>Risk:</b> {_esc(fix.risk_level.value if hasattr(fix.risk_level,'value') else fix.risk_level)}  |  "
                    f"<b>Explanation:</b> {_esc(fix.explanation)}",
                    self.styles['AvBody']))
                if fix.original_code:
                    block.append(Paragraph("<b>Before:</b>", self.styles['AvMuted']))
                    block.append(Preformatted(_esc(fix.original_code), self.styles['AvCode']))
                block.append(Paragraph("<b>After:</b>", self.styles['AvMuted']))
                block.append(Preformatted(_esc(fix.replacement_code), self.styles['AvCode']))
                story.append(KeepTogether(block))
                story.append(Spacer(1, 0.15*inch))

        if n == 0:
            story.append(Paragraph("No fixes were suggested.", self.styles['AvMuted']))
        return story

    # ── Applied fixes ─────────────────────────────────────────────────────────

    def _applied_fixes_section(self, sr) -> list:
        story = [Paragraph("Applied Fixes", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_SUCCESS))
        story.append(Spacer(1, 0.1*inch))

        if not sr.applied_fixes:
            story.append(Paragraph("No fixes were applied during this session.", self.styles['AvMuted']))
            return story

        for i, fix in enumerate(sr.applied_fixes, 1):
            block = []
            lines = f"lines {fix.start_line}-{fix.end_line}" if (fix.start_line and fix.end_line) else ""
            block.append(Paragraph(
                f"<b>Applied Fix {i}: {_esc(fix.file_path)}</b> {lines}",
                self.styles['AvBold']))
            block.append(Paragraph(
                f"<b>Status:</b> Fix applied successfully  |  "
                f"<b>Risk:</b> {_esc(fix.risk_level)}  |  "
                f"<b>Applied:</b> {fix.applied_at.strftime('%Y-%m-%d %H:%M:%S')}",
                self.styles['AvBody']))
            block.append(Paragraph(f"<i>{_esc(fix.explanation)}</i>", self.styles['AvBody']))
            if fix.original_code:
                block.append(Paragraph("<b>Before:</b>", self.styles['AvMuted']))
                block.append(Preformatted(_esc(fix.original_code), self.styles['AvCode']))
            block.append(Paragraph("<b>After:</b>", self.styles['AvMuted']))
            block.append(Preformatted(_esc(fix.replacement_code), self.styles['AvCode']))
            story.append(KeepTogether(block))
            story.append(Spacer(1, 0.15*inch))

        return story

    # ── IBM Bob usage proof ───────────────────────────────────────────────────

    def _bob_usage_section(self) -> list:
        story = [Paragraph("IBM Bob Integration", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_PRIMARY))
        story.append(Spacer(1, 0.1*inch))

        story.append(Paragraph(
            "IBM Bob was used to perform AI-powered diagnosis of training anomalies:",
            self.styles['AvBody']))
        story.append(Spacer(1, 0.06*inch))

        steps = [
            "Receive structured anomaly context from Aviexa (telemetry + source code).",
            "Analyze gradient norms, loss curves, and memory metrics for root causes.",
            "Generate ranked root-cause hypotheses with confidence scores.",
            "Recommend specific code fixes with line numbers, risk levels, and explanations.",
            "Deliver the diagnosis to the VS Code panel and this PDF report.",
        ]
        for idx, step in enumerate(steps, 1):
            story.append(Paragraph(f"{idx}. {_esc(step)}", self.styles['AvNumbered']))

        story.append(Spacer(1, 0.15*inch))
        story.append(Paragraph(
            "For local demo reliability, Aviexa uses the BobClient adapter in mock mode "
            "unless a live IBM Bob API endpoint is configured via the IBM_BOB_API_KEY "
            "environment variable.",
            self.styles['AvMuted']))
        return story

    # ── Appendix ──────────────────────────────────────────────────────────────

    def _appendix(self, sr) -> list:
        story = [Paragraph("Appendix: Raw Session Metadata", self.styles['AvSection'])]
        story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER))
        story.append(Spacer(1, 0.1*inch))

        meta_text = _esc(json.dumps(sr.metadata, indent=2))
        story.append(Preformatted(meta_text, self.styles['AvCode']))

        if sr.anomalies:
            story.append(Spacer(1, 0.15*inch))
            story.append(Paragraph("<b>Anomaly Type Breakdown:</b>", self.styles['AvBold']))
            breakdown: dict = {}
            for a in sr.anomalies:
                k = str(a.anomaly_type)
                breakdown[k] = breakdown.get(k, 0) + 1
            story.append(Preformatted(_esc(json.dumps(breakdown, indent=2)), self.styles['AvCode']))

        return story
