# Instrucciones del repositorio

Estas instrucciones se aplican a todo el repositorio. Deben leerse antes de iniciar cualquier tarea y complementan las instrucciones globales vigentes.

## Protocolo obligatorio de trazabilidad y auditoría en GitHub

1. Al iniciar cualquier tarea, leer primero `AGENTS.md`.

2. Todo informe, evidencia, benchmark, script de verificación, fixture, resultado reproducible o documento que sea necesario para auditoría externa debe quedar versionado en Git.

3. Antes de declarar una tarea de auditoría o corrección como terminada, los archivos necesarios para revisarla deben:
   - estar guardados;
   - estar añadidos a Git;
   - tener commit;
   - estar enviados al repositorio remoto GitHub mediante push.

4. No basta con decir que un archivo existe localmente.

5. La respuesta final de Codex debe indicar siempre:
   - repositorio;
   - rama;
   - commit SHA;
   - archivos creados;
   - archivos modificados;
   - comandos de validación ejecutados;
   - resultados de tests;
   - si el push a GitHub fue exitoso.

6. Si el push falla, la tarea NO debe declararse completada. Debe informarse el error exacto.

7. Para cambios de código de producción:
   - no trabajar directamente sobre `main` salvo autorización explícita;
   - crear una rama específica;
   - hacer commit;
   - hacer push;
   - informar rama y SHA;
   - esperar revisión antes de merge.

8. Los documentos y scripts de auditoría también deben subirse a GitHub, aunque no modifiquen código de producción.

9. Nunca subir:
   - `.env`;
   - credenciales;
   - API keys;
   - tokens;
   - licencias;
   - archivos secretos;
   - `.venv`;
   - cachés;
   - logs con información sensible;
   - binarios grandes innecesarios.

10. Antes de cada commit revisar:

    ```text
    git status
    git diff
    ```

    y verificar que no se esté incluyendo información sensible.

11. Los scripts ad hoc utilizados para demostrar hallazgos matemáticos importantes no deben quedar únicamente en consola. Si sustentan una auditoría, deben convertirse en scripts reproducibles dentro del repositorio.

12. No eliminar evidencia histórica de auditoría sin autorización explícita.

13. Cuando un resultado de auditoría contradiga un test existente, no modificar producción para conservar el test. Primero documentar la contradicción y determinar cuál formulación es correcta.

14. Cada trabajo debe distinguir claramente:
    - evidencia observada;
    - interpretación;
    - conclusión;
    - cambios implementados.

15. Las afirmaciones matemáticas importantes deben ser reproducibles desde archivos versionados en el repositorio.
