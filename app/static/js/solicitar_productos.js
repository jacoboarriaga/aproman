/**
 * solicitar_productos.js
 * Lógica dinámica para el formulario de Solicitud de Pintura.
 * Maneja: filas dinámicas, búsqueda de productos vía API, existencias y totales.
 */

let filaCount = 0;

// -------------------------------------------------------
// Agregar una nueva fila vacía a la tabla de productos
// -------------------------------------------------------
function agregarFila() {
    filaCount++;
    const tbody = document.getElementById('tbody-productos');
    const tr = document.createElement('tr');
    tr.id = `fila-${filaCount}`;

    tr.innerHTML = `
        <td data-label="Código">
            <input type="text"
                   name="codigo[]"
                   id="codigo-${filaCount}"
                   class="form-control"
                   placeholder="Ej. 0403000-05"
                   autocomplete="off"
                   onblur="buscarProducto(${filaCount})"
                   required>
        </td>
        <td data-label="Descripción del Producto">
            <input type="text"
                   id="nombre-${filaCount}"
                   class="form-control"
                   placeholder="Producto..."
                   readonly
                   tabindex="-1">
        </td>
        <td data-label="Precio Unit.">
            <div class="precio-wrapper">
                <span class="precio-prefix">$</span>
                <input type="number"
                       id="precio-${filaCount}"
                       name="precio[]"
                       class="form-control numeric-input"
                       readonly
                       tabindex="-1">
            </div>
        </td>
        <td data-label="Existencias">
            <span id="existencias-${filaCount}" class="stock-ok">—</span>
            <input type="hidden" id="existencias-val-${filaCount}" value="0">
            <input type="hidden" id="unidad-${filaCount}" name="unidad_medida[]" value="">
        </td>
        <td data-label="Cantidad">
            <input type="number"
                   id="cantidad-${filaCount}"
                   name="cantidad[]"
                   class="form-control numeric-input"
                   min="0.01"
                   step="0.01"
                   value="1"
                   onchange="calcularSubtotal(${filaCount})"
                   onkeyup="calcularSubtotal(${filaCount})"
                   required>
        </td>
        <td data-label="Subtotal">
            <div class="subtotal-cell">
                <span>$</span>
                <span id="subtotal-txt-${filaCount}">0.00</span>
                <input type="hidden" id="subtotal-${filaCount}" class="subtotal-input" value="0">
            </div>
        </td>
        <td class="td-accion" style="text-align:center;">
            <button type="button" class="btn-eliminar-fila" onclick="eliminarFila(${filaCount})" title="Eliminar fila">
                ✕
            </button>
        </td>
    `;

    tbody.appendChild(tr);
}

// -------------------------------------------------------
// Buscar producto en el API del backend
// -------------------------------------------------------
function buscarProducto(id) {
    const codigoInput = document.getElementById(`codigo-${id}`);
    const bodegaSelect = document.getElementById('cod_bodega');

    if (!codigoInput || !bodegaSelect) return;

    const codigo  = codigoInput.value.trim().toUpperCase();
    const bodega  = bodegaSelect.value;

    const nombreInput      = document.getElementById(`nombre-${id}`);
    const precioInput      = document.getElementById(`precio-${id}`);
    const existenciasSpan  = document.getElementById(`existencias-${id}`);
    const existenciasVal   = document.getElementById(`existencias-val-${id}`);
    const unidadInput      = document.getElementById(`unidad-${id}`);

    // Limpiar si el código está vacío
    if (!codigo) {
        limpiarFila(id);
        return;
    }

    // Validar que ya se haya seleccionado una bodega
    if (!bodega) {
        existenciasSpan.textContent = 'Seleccione bodega';
        existenciasSpan.className = 'stock-warning';
        return;
    }

    // Indicador de carga
    nombreInput.value        = 'Buscando...';
    existenciasSpan.textContent = '...';
    existenciasSpan.className   = '';

    fetch(`/sistemas/api/producto?codigo=${encodeURIComponent(codigo)}&bodega=${encodeURIComponent(bodega)}`)
        .then(resp => resp.json())
        .then(data => {
            if (data.error) {
                limpiarFila(id);
                nombreInput.value = 'Producto no encontrado';
                existenciasSpan.textContent = '—';
                existenciasSpan.className   = 'stock-warning';
                return;
            }

            nombreInput.value             = data.nombre;
            precioInput.value             = parseFloat(data.precio).toFixed(4);
            existenciasVal.value          = data.existencias;
            unidadInput.value             = data.unidad_medida;
            existenciasSpan.textContent   = data.existencias;
            existenciasSpan.className     = parseFloat(data.existencias) > 0 ? 'stock-ok' : 'stock-warning';

            calcularSubtotal(id);
        })
        .catch(err => {
            console.error('Error buscando producto:', err);
            limpiarFila(id);
            nombreInput.value = 'Error al buscar';
        });
}

// -------------------------------------------------------
// Limpiar una fila al no encontrar el producto
// -------------------------------------------------------
function limpiarFila(id) {
    const nombreInput     = document.getElementById(`nombre-${id}`);
    const precioInput     = document.getElementById(`precio-${id}`);
    const existenciasSpan = document.getElementById(`existencias-${id}`);
    const existenciasVal  = document.getElementById(`existencias-val-${id}`);
    const unidadInput     = document.getElementById(`unidad-${id}`);

    if (nombreInput)     nombreInput.value           = '';
    if (precioInput)     precioInput.value            = '';
    if (existenciasSpan) existenciasSpan.textContent  = '—';
    if (existenciasSpan) existenciasSpan.className    = '';
    if (existenciasVal)  existenciasVal.value         = '0';
    if (unidadInput)     unidadInput.value            = '';

    calcularSubtotal(id);
}

// -------------------------------------------------------
// Calcular subtotal de una fila y actualizar el total
// -------------------------------------------------------
function calcularSubtotal(id) {
    const precio   = parseFloat(document.getElementById(`precio-${id}`)?.value)   || 0;
    const cantidad = parseFloat(document.getElementById(`cantidad-${id}`)?.value) || 0;
    const subtotal = precio * cantidad;

    document.getElementById(`subtotal-txt-${id}`).innerText = subtotal.toFixed(2);
    document.getElementById(`subtotal-${id}`).value        = subtotal;

    // Validación visual de stock
    const existencias = parseFloat(document.getElementById(`existencias-val-${id}`)?.value) || 0;
    const cantInput   = document.getElementById(`cantidad-${id}`);
    const exSpan      = document.getElementById(`existencias-${id}`);

    if (existencias > 0) {
        if (cantidad > existencias) {
            cantInput?.classList.add('stock-warning');
            if (exSpan) exSpan.className = 'stock-warning';
        } else {
            cantInput?.classList.remove('stock-warning');
            if (exSpan) exSpan.className = 'stock-ok';
        }
    }

    calcularTotalGral();
}

// -------------------------------------------------------
// Calcular el total general sumando todos los subtotales
// -------------------------------------------------------
function calcularTotalGral() {
    const subtotales = document.querySelectorAll('.subtotal-input');
    let total = 0;
    subtotales.forEach(input => {
        total += parseFloat(input.value) || 0;
    });
    const totalEl = document.getElementById('total-estimado');
    if (totalEl) totalEl.innerText = '$' + total.toFixed(2);
}

// -------------------------------------------------------
// Eliminar una fila de la tabla
// -------------------------------------------------------
function eliminarFila(id) {
    const tr = document.getElementById(`fila-${id}`);
    if (tr) tr.remove();
    calcularTotalGral();
}

// -------------------------------------------------------
// Validar stock antes de enviar el formulario
// -------------------------------------------------------
function validarFormulario(event) {
    const filas = document.querySelectorAll('#tbody-productos tr');
    let hayError = false;

    filas.forEach(tr => {
        const id = tr.id.replace('fila-', '');
        const cantidad    = parseFloat(document.getElementById(`cantidad-${id}`)?.value) || 0;
        const existencias = parseFloat(document.getElementById(`existencias-val-${id}`)?.value) || 0;
        const codigo      = document.getElementById(`codigo-${id}`)?.value.trim();

        if (codigo && existencias > 0 && cantidad > existencias) {
            hayError = true;
        }
    });

    if (hayError) {
        const confirmacion = confirm(
            '⚠️ Hay productos cuya cantidad supera las existencias en bodega.\n' +
            '¿Deseas continuar de todas formas?'
        );
        if (!confirmacion) {
            event.preventDefault();
            return false;
        }
    }

    return true;
}

// -------------------------------------------------------
// Inicialización al cargar la página
// -------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {
    agregarFila();
});
