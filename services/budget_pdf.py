"""Generación del PDF de presupuesto con ReportLab.

Adaptado del sistema original de Vielma, con la paleta del sistema (acento
naranja) en lugar del azul original. Mantiene los datos del taller.
"""
from io import BytesIO
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer, Image)

# Datos del negocio (se mantienen tal cual del sistema original).
NOMBRE_NEGOCIO = "VIELMA MOTO-REPUESTOS"
DIRECCION_LINEA1 = "Oceanía, casi Sapirangy"
DIRECCION_LINEA2 = "Barrio 8 de Diciembre, Villa Elisa"
PROPIETARIO = "Propietario: Christian Vielma"

# Paleta del sistema (naranja de Vielma) para reemplazar el azul original.
COLOR_PRIMARIO = HexColor("#ff6a00")
COLOR_SECUNDARIO = HexColor("#c85400")
COLOR_ACENTO = HexColor("#ff6a00")
COLOR_GRIS_CLARO = HexColor("#f5f5f5")
COLOR_GRIS = HexColor("#e0e0e0")
COLOR_TEXTO = HexColor("#212121")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def formatear_guaranies(valor):
    """Formatea un número como guaraníes: 'Gs 1.500.000'."""
    try:
        valor_int = int(round(float(valor)))
    except (ValueError, TypeError):
        valor_int = 0
    texto = f"{valor_int:,}".replace(",", ".")
    return f"Gs {texto}"


def generar_pdf(datos):
    """Genera el PDF del presupuesto. Devuelve un BytesIO.

    datos: dict con numero, fecha, tipo_vehiculo, marca, modelo, color, anio,
           repuestos (lista de {descripcion, valor_unitario, cantidad, subtotal})
           y total.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm,
                            leftMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=2 * cm)
    elements = []
    width_disponible = A4[0] - 4 * cm
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Heading1'],
                                   fontName='Helvetica-Bold', fontSize=20,
                                   textColor=COLOR_PRIMARIO, alignment=TA_CENTER,
                                   spaceAfter=2 * mm)
    estilo_subtitulo = ParagraphStyle('Subtitulo', parent=styles['Normal'],
                                      fontName='Helvetica', fontSize=10,
                                      textColor=COLOR_SECUNDARIO, alignment=TA_CENTER,
                                      spaceAfter=1 * mm)
    estilo_seccion = ParagraphStyle('Seccion', parent=styles['Heading2'],
                                    fontName='Helvetica-Bold', fontSize=12,
                                    textColor=COLOR_PRIMARIO, spaceBefore=6 * mm,
                                    spaceAfter=3 * mm)
    estilo_normal = ParagraphStyle('NormalCustom', parent=styles['Normal'],
                                   fontName='Helvetica', fontSize=10, textColor=COLOR_TEXTO)
    estilo_pie = ParagraphStyle('Pie', parent=styles['Normal'],
                                fontName='Helvetica-Oblique', fontSize=9,
                                textColor=COLOR_SECUNDARIO, alignment=TA_CENTER,
                                spaceBefore=10 * mm)
    estilo_pie_dir = ParagraphStyle('PieDir', parent=styles['Normal'],
                                    fontName='Helvetica', fontSize=8,
                                    textColor=HexColor("#757575"), alignment=TA_CENTER,
                                    spaceBefore=2 * mm)

    # --- Encabezado con logo (si existe un PNG/JPG) ---
    logo_path = None
    for candidate in ("logo.png", "logo.jpg", "logo.jpeg"):
        p = os.path.join(BASE_DIR, "static", "img", candidate)
        if os.path.exists(p):
            logo_path = p
            break

    if logo_path:
        logo_img = Image(logo_path, width=22 * mm, height=22 * mm)
        logo_img.hAlign = 'RIGHT'
        header_table = Table([[Paragraph(NOMBRE_NEGOCIO, estilo_titulo), logo_img]],
                             colWidths=[width_disponible - 26 * mm, 26 * mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph(NOMBRE_NEGOCIO, estilo_titulo))

    elements.append(Paragraph(DIRECCION_LINEA1, estilo_subtitulo))
    elements.append(Paragraph(DIRECCION_LINEA2, estilo_subtitulo))
    elements.append(Paragraph(PROPIETARIO, estilo_subtitulo))
    elements.append(Spacer(1, 4 * mm))

    linea_table = Table([['', '']], colWidths=[width_disponible])
    linea_table.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 2, COLOR_PRIMARIO)]))
    elements.append(linea_table)
    elements.append(Spacer(1, 4 * mm))

    # --- Título PRESUPUESTO ---
    estilo_pres_titulo = ParagraphStyle('PresTitulo', parent=styles['Heading1'],
                                        fontName='Helvetica-Bold', fontSize=16,
                                        textColor=COLOR_ACENTO, alignment=TA_CENTER,
                                        spaceAfter=3 * mm)
    elements.append(Paragraph("PRESUPUESTO", estilo_pres_titulo))

    info_table = Table([[
        Paragraph(f"<b>Número:</b> {datos['numero']}", estilo_normal),
        Paragraph(f"<b>Fecha:</b> {datos['fecha']}", estilo_normal),
    ]], colWidths=[width_disponible / 2, width_disponible / 2])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    # --- Datos del vehículo ---
    elements.append(Paragraph("DATOS DEL VEHÍCULO", estilo_seccion))
    vehiculo_data = [
        [Paragraph("<b>Tipo:</b>", estilo_normal), Paragraph(datos.get('tipo_vehiculo', ''), estilo_normal),
         Paragraph("<b>Marca:</b>", estilo_normal), Paragraph(datos.get('marca', ''), estilo_normal)],
        [Paragraph("<b>Modelo:</b>", estilo_normal), Paragraph(datos.get('modelo', ''), estilo_normal),
         Paragraph("<b>Color:</b>", estilo_normal), Paragraph(datos.get('color', ''), estilo_normal)],
        [Paragraph("<b>Año:</b>", estilo_normal), Paragraph(datos.get('anio', ''), estilo_normal), '', ''],
    ]
    col_w = width_disponible / 4
    vehiculo_table = Table(vehiculo_data,
                           colWidths=[col_w * 0.6, col_w * 1.4, col_w * 0.6, col_w * 1.4])
    vehiculo_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_CLARO),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_GRIS),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, COLOR_GRIS),
    ]))
    elements.append(vehiculo_table)
    elements.append(Spacer(1, 6 * mm))

    # --- Tabla de repuestos ---
    elements.append(Paragraph("REPUESTOS", estilo_seccion))
    estilo_header = ParagraphStyle('HeaderTabla', parent=styles['Normal'],
                                   fontName='Helvetica-Bold', fontSize=10,
                                   textColor=white, alignment=TA_CENTER)
    estilo_celda = ParagraphStyle('CeldaTabla', parent=styles['Normal'],
                                  fontName='Helvetica', fontSize=10,
                                  textColor=COLOR_TEXTO, alignment=TA_CENTER)
    estilo_celda_izq = ParagraphStyle('CeldaTablaIzq', parent=styles['Normal'],
                                      fontName='Helvetica', fontSize=10,
                                      textColor=COLOR_TEXTO, alignment=TA_LEFT)
    estilo_celda_der = ParagraphStyle('CeldaTablaDer', parent=styles['Normal'],
                                      fontName='Helvetica', fontSize=10,
                                      textColor=COLOR_TEXTO, alignment=TA_RIGHT)

    tabla_data = [[
        Paragraph("Cant.", estilo_header),
        Paragraph("Descripción", estilo_header),
        Paragraph("Valor Unitario", estilo_header),
        Paragraph("Subtotal", estilo_header),
    ]]
    for r in datos['repuestos']:
        tabla_data.append([
            Paragraph(str(r['cantidad']), estilo_celda),
            Paragraph(r['descripcion'], estilo_celda_izq),
            Paragraph(formatear_guaranies(r['valor_unitario']), estilo_celda_der),
            Paragraph(formatear_guaranies(r['subtotal']), estilo_celda_der),
        ])

    col_widths = [width_disponible * 0.10, width_disponible * 0.40,
                  width_disponible * 0.25, width_disponible * 0.25]
    tabla_repuestos = Table(tabla_data, colWidths=col_widths)
    estilo_tabla = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARIO),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_PRIMARIO),
        ('LINEBELOW', (0, 0), (-1, 0), 1, COLOR_PRIMARIO),
        ('INNERGRID', (0, 1), (-1, -1), 0.5, COLOR_GRIS),
    ]
    for i in range(1, len(tabla_data)):
        if i % 2 == 0:
            estilo_tabla.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS_CLARO))
    tabla_repuestos.setStyle(TableStyle(estilo_tabla))
    elements.append(tabla_repuestos)
    elements.append(Spacer(1, 4 * mm))

    # --- Total ---
    estilo_total = ParagraphStyle('Total', parent=styles['Normal'],
                                  fontName='Helvetica-Bold', fontSize=14,
                                  textColor=COLOR_PRIMARIO, alignment=TA_RIGHT)
    total_table = Table([['', Paragraph(
        f"<b>TOTAL: {formatear_guaranies(datos['total'])}</b>", estilo_total)]],
        colWidths=[width_disponible * 0.5, width_disponible * 0.5])
    total_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
        ('LINEABOVE', (0, 0), (-1, 0), 1.5, COLOR_PRIMARIO),
    ]))
    elements.append(total_table)

    # --- Pie ---
    elements.append(Spacer(1, 15 * mm))
    linea_pie = Table([['', '']], colWidths=[width_disponible])
    linea_pie.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.5, COLOR_GRIS)]))
    elements.append(linea_pie)
    elements.append(Paragraph("Gracias por confiar en Vielma Moto-Repuestos.", estilo_pie))
    elements.append(Paragraph(f"{DIRECCION_LINEA1} - {DIRECCION_LINEA2}", estilo_pie_dir))

    doc.build(elements)
    buffer.seek(0)
    return buffer
