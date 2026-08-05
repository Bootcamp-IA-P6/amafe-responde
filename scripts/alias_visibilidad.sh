# alias_visibilidad.sh — funciones de visibilidad para amafe-responde
#
# NO se carga solo. Actívalas con:
#     source scripts/alias_visibilidad.sh
#
# Cuatro funciones, dos por sentido:
#     vis_repliegue        simula el paso a privado (dry-run, no toca nada)
#     vis_repliegue_real   lo aplica de verdad (pide confirmacion)
#     vis_despliegue       simula la vuelta a publico (dry-run)
#     vis_despliegue_real  la aplica de verdad (pide confirmacion)
#     vis_estado           lee el estado actual sin cambiar nada
#
# Recordatorio: Streamlit es MANUAL en ambos sentidos (no tiene API).

VIS_SCRIPT="scripts/visibilidad_20260801170139S.py"

_vis_raiz() {
    git rev-parse --show-toplevel 2>/dev/null || {
        echo "vis: no estas dentro del repo" >&2
        return 1
    }
}

_vis_ejecuta() {  # $1 = etiqueta, $2 = --revertir o vacio, $3 = --ejecutar o vacio
    local raiz
    raiz=$(_vis_raiz) || return 1
    if [ ! -f "$raiz/$VIS_SCRIPT" ]; then
        echo "vis: no encuentro $VIS_SCRIPT en $raiz" >&2
        return 1
    fi
    if [ -n "$3" ]; then
        echo "Vas a $1 DE VERDAD: HF Space, repo y Project #77." >&2
        echo "Streamlit hay que cambiarlo a mano en share.streamlit.io." >&2
        read -r -p "Escribe 'si' para continuar: " respuesta
        [ "$respuesta" = "si" ] || { echo "Cancelado." >&2; return 1; }
    fi
    ( cd "$raiz" && uv run python "$VIS_SCRIPT" $2 $3 )
}

vis_repliegue()       { _vis_ejecuta "REPLEGAR A PRIVADO" ""          ""; }
vis_repliegue_real()  { _vis_ejecuta "REPLEGAR A PRIVADO" ""          "--ejecutar"; }
vis_despliegue()      { _vis_ejecuta "DESPLEGAR A PUBLICO" "--revertir" ""; }
vis_despliegue_real() { _vis_ejecuta "DESPLEGAR A PUBLICO" "--revertir" "--ejecutar"; }

vis_estado() {
    local raiz
    raiz=$(_vis_raiz) || return 1
    ( cd "$raiz" && uv run python "$VIS_SCRIPT" 2>/dev/null |
        python -c "
import json, sys
d = json.load(sys.stdin)
for a in d['activos']:
    print(f\"{a['activo']:10} {a.get('antes', {})}\")
print('streamlit  (manual, comprobar en ventana privada)')" )
}

echo "vis: funciones cargadas -> vis_estado, vis_repliegue[_real], vis_despliegue[_real]" >&2
