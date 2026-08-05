### reversion_manual.md

# Reversión manual a público

Red de seguridad por si `--revertir` falla. Vía normal:

    uv run python scripts/visibilidad_20260801170139S.py --revertir --ejecutar

## 1. Streamlit (MANUAL, no hay API)

share.streamlit.io -> app amafe-responde -> Settings -> Sharing
-> "Anyone with the link can view this app"

## 2. Repo GitHub

```bash
gh repo edit Bootcamp-IA-P6/amafe-responde --visibility public \
  --accept-visibility-change-consequences
```

## 3. Project #77

```bash
gh project edit 77 --owner Bootcamp-IA-P6 --visibility PUBLIC
```

## 4. HF Space

```bash
uv run python -c "
from huggingface_hub import HfApi
a = HfApi()
a.update_repo_settings(repo_id='JJRSE/amafe-responde', repo_type='space', private=False)
a.restart_space('JJRSE/amafe-responde')"
```

## Notas

- Requiere `HF_TOKEN` en `.env` y `gh` autenticado con scopes `repo`, `project`.
- Las stars y watchers perdidos al privatizar **no se recuperan**.
- El Space quedará `RUNNING` aunque antes estuviera `SLEEPING`. Volverá a
  dormirse solo por inactividad.
- Verificar en ventana privada: los cuatro recursos deben cargar sin sesión.