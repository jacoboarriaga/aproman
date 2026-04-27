"""
pdf_utils.py - Reporte Final de Proyecto
Diseno compacto, hoja blanca, texto negro y tablas neutras.
"""
import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

C_BLACK = colors.HexColor("#000000")
C_MID = colors.HexColor("#000000")
C_SUBTLE = colors.HexColor("#000000")
C_BORDER = colors.HexColor("#000000")
C_HDR_BG = colors.white
C_ALT = colors.white
C_WHITE = colors.white

PAGE_W, PAGE_H = letter
MARGIN = 14 * mm


def _styles():
    base = getSampleStyleSheet()

    def P(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title": P("title", fontName="Helvetica-Bold", fontSize=14, textColor=C_BLACK, leading=17),
        "subtitle": P("subtitle", fontName="Helvetica", fontSize=7, textColor=C_BLACK, leading=10),
        "section": P(
            "section",
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=C_BLACK,
            spaceBefore=2,
            spaceAfter=3,
            leading=10,
        ),
        "sistema": P(
            "sistema",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=C_BLACK,
            leading=12,
            spaceBefore=6,
            spaceAfter=2,
        ),
        "subsec": P(
            "subsec",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=C_BLACK,
            spaceBefore=5,
            spaceAfter=2,
            leading=10,
        ),
        "lbl": P("lbl", fontName="Helvetica-Bold", fontSize=7, textColor=C_BLACK, leading=9),
        "val": P("val", fontName="Helvetica", fontSize=8, textColor=C_BLACK, leading=10),
        "tbl_hdr": P("tbl_hdr", fontName="Helvetica-Bold", fontSize=7, textColor=C_BLACK, leading=9),
        "tbl_cell": P("tbl_cell", fontName="Helvetica", fontSize=7, textColor=C_BLACK, leading=9),
        "tbl_bold": P("tbl_bold", fontName="Helvetica-Bold", fontSize=7, textColor=C_BLACK, leading=9),
        "total": P("total", fontName="Helvetica-Bold", fontSize=8, textColor=C_BLACK, leading=10),
        "empty": P("empty", fontName="Helvetica-Oblique", fontSize=7, textColor=C_BLACK, leading=9),
    }


def _tbl_style(n_rows, right_from=None):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_BLACK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -1), C_WHITE),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_BLACK),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOX", (0, 0), (-1, -1), 0.6, C_BORDER),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_BLACK),
        ("INNERGRID", (0, 1), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if right_from is not None:
        cmds.append(("ALIGN", (right_from, 0), (-1, -1), "RIGHT"))
    return TableStyle(cmds)


def _page_fn(proyecto):
    codigo = proyecto.get("codigo", "")
    cliente = proyecto.get("cliente_nombre", "")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    def fn(canvas, doc):
        canvas.saveState()
        w, h = letter
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 11 * mm, w - MARGIN, 11 * mm)
        canvas.setFont("Helvetica", 6)
        canvas.setFillColor(C_BLACK)
        canvas.drawString(MARGIN, 7.5 * mm, f"Proyecto: {codigo}  |  Cliente: {cliente}")
        canvas.drawCentredString(w / 2, 7.5 * mm, f"Pagina {doc.page}")
        canvas.drawRightString(w - MARGIN, 7.5 * mm, f"Generado: {now}")
        canvas.restoreState()

    return fn


def _build_info(proyecto, uw, S, logo_path):
    story = []
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    title_block = Table(
        [
            [Paragraph("REPORTE FINAL DE PROYECTO", S["title"])],
            [Paragraph(f"Codigo del proyecto: {proyecto.get('codigo', '-')}", S["subsec"])],
            [Paragraph(f"Generado el {now}", S["subtitle"])],
        ],
        colWidths=[uw * 0.60],
        style=TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        ),
    )

    if logo_path and os.path.exists(logo_path):
        logo_cell = RLImage(logo_path, width=44 * mm, height=18 * mm, kind="proportional")
    else:
        logo_cell = Paragraph("[LOGO]", S["subtitle"])

    header_row = Table(
        [[title_block, logo_cell]],
        colWidths=[uw * 0.62, uw * 0.38],
        style=TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (0, 0), "BOTTOM"),
                ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        ),
    )
    story.append(header_row)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width=uw, thickness=0.6, color=C_BORDER, spaceAfter=6))

    def side_tbl(rows, w):
        data = [[Paragraph(lbl, S["lbl"]), Paragraph(str(val) if val else "-", S["val"])] for lbl, val in rows]
        t = Table(data, colWidths=[w * 0.36, w * 0.64])
        t.setStyle(
            TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, C_BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return t

    cw = uw / 2 - 5
    left = [
        ("CODIGO", proyecto.get("codigo", "")),
        ("FECHA CREACION", proyecto.get("fecha_formateada", "")),
        ("ESTADO", str(proyecto.get("estado", "")).upper()),
        ("AGENTE ASIGNADO", proyecto.get("agente_nombre", "N/A")),
    ]
    right = [
        ("COD. CLIENTE", proyecto.get("cod_cliente", "")),
        ("CLIENTE", proyecto.get("cliente_nombre", "")),
        ("DUI / NIT", proyecto.get("cliente_dui_nit", "")),
        ("TELEFONO", proyecto.get("cliente_telefono", "")),
        ("EMAIL", proyecto.get("cliente_email", "")),
        ("DIRECCION", proyecto.get("cliente_direccion", "")),
    ]

    combo = Table(
        [[side_tbl(left, cw), Spacer(10, 1), side_tbl(right, cw)]],
        colWidths=[cw, 10, cw],
        style=TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        ),
    )
    story.append(combo)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width=uw, thickness=0.6, color=C_BORDER, spaceAfter=3))
    return story


def _build_indicadores(sis, uw, S):
    def fm(v):
        try:
            return f"${float(v):,.2f}"
        except Exception:
            return str(v) if v is not None else "-"

    def fv(v):
        return str(v) if v is not None else "-"

    rows = [
        [Paragraph(h, S["tbl_hdr"]) for h in ["Indicador", "Valor Inicial (Estimado)", "Valor Final (Cierre)"]],
        [Paragraph("Precio por M2 ($)", S["tbl_cell"]), Paragraph(fm(sis.get("monto_inicial")), S["tbl_cell"]), Paragraph(fm(sis.get("monto_final")), S["tbl_bold"])],
        [Paragraph("Metros Cuadrados", S["tbl_cell"]), Paragraph(fv(sis.get("metros_cuadrados_iniciales")), S["tbl_cell"]), Paragraph(fv(sis.get("metros_cuadrados_finales")), S["tbl_bold"])],
        [Paragraph("Monto Servicio ($)", S["tbl_cell"]), Paragraph(fm(sis.get("costo_servicio_m2_inicial")), S["tbl_cell"]), Paragraph(fm(sis.get("costo_servicio_m2_final")), S["tbl_bold"])],
        [Paragraph("Producto Terminado M2", S["tbl_cell"]), Paragraph(fm(sis.get("producto_terminado_inicial")), S["tbl_cell"]), Paragraph(fm(sis.get("producto_terminado_final")), S["tbl_bold"])],
        [Paragraph("Hombres por Dia", S["tbl_cell"]), Paragraph(fv(sis.get("hombres_por_dia_iniciales")), S["tbl_cell"]), Paragraph(fv(sis.get("hombres_por_dia_finales")), S["tbl_bold"])],
    ]
    t = Table(rows, colWidths=[uw * 0.46, uw * 0.27, uw * 0.27], style=_tbl_style(len(rows), right_from=1))
    return [Paragraph("Indicadores", S["subsec"]), t, Spacer(1, 6)]


def _build_materiales(mats, uw, S):
    story = [Paragraph("Materiales Utilizados", S["subsec"])]
    if not mats:
        return story + [Paragraph("Sin materiales registrados.", S["empty"]), Spacer(1, 3)]

    def fm(v):
        try:
            return f"${float(v):,.2f}" if v is not None else "-"
        except Exception:
            return "-"

    rows = [[Paragraph(h, S["tbl_hdr"]) for h in ["Fecha", "Material", "Costo", "Descripcion"]]]
    total_mats = 0.0
    for m in mats:
        costo = m.get("costo_material")
        try:
            total_mats += float(costo or 0)
        except Exception:
            pass

        rows.append(
            [
                Paragraph(str(m.get("fecha_formateada") or "-"), S["tbl_cell"]),
                Paragraph(str(m.get("material_nombre") or "-"), S["tbl_cell"]),
                Paragraph(fm(costo), S["tbl_cell"]),
                Paragraph(str(m.get("descripcion") or "-"), S["tbl_cell"]),
            ]
        )

    if total_mats > 0:
        rows.append([Paragraph("<b>TOTAL MATERIALES</b>", S["tbl_bold"]), "", Paragraph(f"<b>${total_mats:,.2f}</b>", S["total"]), ""])

    ts = _tbl_style(len(rows))
    if total_mats > 0:
        ts.add("BACKGROUND", (0, -1), (-1, -1), C_WHITE)
        ts.add("LINEABOVE", (0, -1), (-1, -1), 0.6, C_BLACK)
        ts.add("SPAN", (0, -1), (1, -1))

    t = Table(rows, colWidths=[uw * 0.15, uw * 0.25, uw * 0.15, uw * 0.45], style=ts)
    return story + [t, Spacer(1, 6)]


def _build_personal(pers, uw, S):
    story = [Paragraph("Mano de Obra / Pintores", S["subsec"])]
    if not pers:
        return story + [Paragraph("Sin pintores asignados.", S["empty"]), Spacer(1, 3)]

    rows = [[Paragraph(h, S["tbl_hdr"]) for h in ["Pintor", "Pago/Dia", "Dias", "Subtotal"]]]
    total = 0.0
    for p in pers:
        ct = p.get("costo_total") or p.get("costo_subtotal", 0)
        try:
            total += float(ct)
        except Exception:
            pass
        rows.append(
            [
                Paragraph(p.get("pintor_nombre", "-"), S["tbl_cell"]),
                Paragraph(f"${float(p.get('pago_dia', 0)):,.2f}", S["tbl_cell"]),
                Paragraph(str(p.get("dias_trabajados", "-")), S["tbl_cell"]),
                Paragraph(f"${float(ct):,.2f}", S["tbl_cell"]),
            ]
        )

    rows.append([Paragraph("<b>TOTAL PINTORES</b>", S["tbl_bold"]), "", "", Paragraph(f"<b>${total:,.2f}</b>", S["total"])])
    ts = _tbl_style(len(rows) - 1, right_from=1)
    ts.add("BACKGROUND", (0, -1), (-1, -1), C_WHITE)
    ts.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    ts.add("LINEABOVE", (0, -1), (-1, -1), 0.6, C_BLACK)
    t = Table(rows, colWidths=[uw * 0.42, uw * 0.18, uw * 0.14, uw * 0.26], style=ts)
    return story + [t, Spacer(1, 6)]


def _build_erp_legacy(erps, uw, S):
    story = [Paragraph("Solicitudes de Despacho (Procolor)", S["subsec"])]
    if not erps:
        return story + [Paragraph("Sin despachos Procolor registrados.", S["empty"]), Spacer(1, 3)]

    rows = [[Paragraph(h, S["tbl_hdr"]) for h in ["N° Doc", "Fecha", "Cod. Prod", "Descripcion", "UM", "Cantidad", "Costo Prom.", "Precio Unit."]]]
    total_erp = 0.0
    for e in erps:
        cantidad = float(e.get("cantidad", e.get("CANTIDAD", 0)))
        precio = float(e.get("precio_unitario") or 0)
        total_erp += cantidad * precio

        fecha = e.get("fecha", "-")
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")
        rows.append(
            [
                Paragraph(str(e.get("num_doc", e.get("NUM_DOCUMENTO", "-"))), S["tbl_cell"]),
                Paragraph(str(fecha), S["tbl_cell"]),
                Paragraph(e.get("codigo", e.get("COD_PRODUCTO", "-")), S["tbl_cell"]),
                Paragraph(e.get("nombre", e.get("nombre_producto", "-")), S["tbl_cell"]),
                Paragraph(e.get("um", e.get("unidad_medida", "-")), S["tbl_cell"]),
                Paragraph(f"{float(e.get('cantidad', e.get('CANTIDAD', 0))):,.2f}", S["tbl_cell"]),
                Paragraph(f"${float(e.get('costo_promedio') or 0):,.2f}", S["tbl_cell"]),
                Paragraph(f"${float(e.get('precio_unitario') or 0):,.2f}", S["tbl_cell"]),
            ]
        )

    if total_erp > 0:
        rows.append(
            [
                Paragraph("<b>TOTAL PRODUCTOS PROCOLOR</b>", S["tbl_bold"]),
                "",
                "",
                "",
                "",
                "",
                "",
                Paragraph(f"<b>${total_erp:,.2f}</b>", S["total"]),
            ]
        )

    ts = _tbl_style(len(rows), right_from=5)
    if total_erp > 0:
        ts.add("BACKGROUND", (0, -1), (-1, -1), C_WHITE)
        ts.add("LINEABOVE", (0, -1), (-1, -1), 0.6, C_BLACK)
        ts.add("SPAN", (0, -1), (6, -1))
        ts.add("ALIGN", (0, -1), (-1, -1), "RIGHT")

    ts.add("LEFTPADDING", (0, 0), (-1, -1), 2)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 2)
    t = Table(
        rows,
        colWidths=[uw * 0.08, uw * 0.10, uw * 0.11, uw * 0.23, uw * 0.08, uw * 0.09, uw * 0.13, uw * 0.18],
        style=ts,
    )
    return story + [t, Spacer(1, 6)]


def _build_erp(erps, uw, S, mostrar_costos=False):
    story = [Paragraph("Solicitudes de Despacho (Procolor)", S["subsec"])]
    if not erps:
        return story + [Paragraph("Sin despachos Procolor registrados.", S["empty"]), Spacer(1, 3)]

    headers = ["N Doc", "Fecha", "Cod. Prod", "Descripcion", "UM", "Cantidad"]
    if mostrar_costos:
        headers.append("Costo Prom.")
    headers.append("Precio Unit.")

    rows = [[Paragraph(h, S["tbl_hdr"]) for h in headers]]
    total_erp = 0.0
    for e in erps:
        cantidad = float(e.get("cantidad", e.get("CANTIDAD", 0)))
        precio = float(e.get("precio_unitario") or 0)
        total_erp += cantidad * precio

        fecha = e.get("fecha", "-")
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")

        row = [
            Paragraph(str(e.get("num_doc", e.get("NUM_DOCUMENTO", "-"))), S["tbl_cell"]),
            Paragraph(str(fecha), S["tbl_cell"]),
            Paragraph(e.get("codigo", e.get("COD_PRODUCTO", "-")), S["tbl_cell"]),
            Paragraph(e.get("nombre", e.get("nombre_producto", "-")), S["tbl_cell"]),
            Paragraph(e.get("um", e.get("unidad_medida", "-")), S["tbl_cell"]),
            Paragraph(f"{cantidad:,.2f}", S["tbl_cell"]),
        ]
        if mostrar_costos:
            row.append(Paragraph(f"${float(e.get('costo_promedio') or 0):,.2f}", S["tbl_cell"]))
        row.append(Paragraph(f"${precio:,.2f}", S["tbl_cell"]))
        rows.append(row)

    if total_erp > 0:
        total_row = [Paragraph("<b>TOTAL PRODUCTOS PROCOLOR</b>", S["tbl_bold"])]
        total_row += [""] * (len(headers) - 2)
        total_row.append(Paragraph(f"<b>${total_erp:,.2f}</b>", S["total"]))
        rows.append(total_row)

    ts = _tbl_style(len(rows), right_from=5)
    if total_erp > 0:
        ts.add("BACKGROUND", (0, -1), (-1, -1), C_WHITE)
        ts.add("LINEABOVE", (0, -1), (-1, -1), 0.6, C_BLACK)
        ts.add("SPAN", (0, -1), (len(headers) - 2, -1))
        ts.add("ALIGN", (0, -1), (-1, -1), "RIGHT")

    ts.add("LEFTPADDING", (0, 0), (-1, -1), 2)
    ts.add("RIGHTPADDING", (0, 0), (-1, -1), 2)

    col_widths = [uw * 0.08, uw * 0.10, uw * 0.11, uw * 0.23, uw * 0.08, uw * 0.09]
    if mostrar_costos:
        col_widths += [uw * 0.13, uw * 0.18]
    else:
        col_widths.append(uw * 0.31)

    t = Table(rows, colWidths=col_widths, style=ts)
    return story + [t, Spacer(1, 6)]


def generar_pdf_proyecto_doc(
    proyecto,
    sistemas,
    personal_por_sistema,
    materiales_por_sistema,
    erp_por_sistema,
    static_folder=None,
    mostrar_costos=False,
):
    buffer = io.BytesIO()
    uw = PAGE_W - 2 * MARGIN
    S = _styles()

    logo_path = None
    if static_folder:
        for name in ("logo_procolor_negro.png", "logo_procolor_negro.jpg", "logo.png", "logo.jpg"):
            candidate = os.path.join(static_folder, "img", name)
            if os.path.exists(candidate):
                logo_path = candidate
                break

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=10 * mm,
        bottomMargin=15 * mm,
        title=f"Reporte {proyecto.get('codigo', '')}",
        author="Sistema de Proyectos",
    )

    on_page = _page_fn(proyecto)
    story = []

    story += _build_info(proyecto, uw, S, logo_path)
    story.append(Paragraph(f"DETALLE DE SISTEMAS  -  {len(sistemas)} sistema{'s' if len(sistemas) != 1 else ''}", S["section"]))

    for sis in sistemas:
        sid = sis["id"]
        nombre = sis.get("sistema_nombre", "Sin nombre")
        codigo = sis.get("sistema_codigo", "")
        label = f"{nombre} ({codigo})" if codigo else nombre

        block = [
            HRFlowable(width=uw, thickness=0.6, color=C_BORDER, spaceAfter=3),
            Paragraph(label, S["sistema"]),
        ]
        block += _build_indicadores(sis, uw, S)
        story.append(KeepTogether(block))

        story += _build_materiales(materiales_por_sistema.get(sid, []), uw, S)
        story += _build_personal(personal_por_sistema.get(sid, []), uw, S)
        story += _build_erp(erp_por_sistema.get(sid, []), uw, S, mostrar_costos=mostrar_costos)
        story.append(Spacer(1, 6))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer
