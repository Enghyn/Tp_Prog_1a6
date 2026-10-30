-- solo_agregado.sql
-- Verificación directa de los triggers RN-15.
-- Ejecutar después de cargar al menos una fila en cada tabla:
--   psql "$DATABASE_URL" -f test/solo_agregado.sql
-- Si una tabla está vacía, el caso se informa como SKIP; no se presenta como
-- una verificación exitosa.

CREATE OR REPLACE FUNCTION pg_temp.assert_solo_agregado_bloqueado(
    p_tabla text,
    p_operacion text,
    p_asignacion text
) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_id integer;
BEGIN
    EXECUTE format('SELECT id FROM %I LIMIT 1', p_tabla) INTO v_id;
    IF v_id IS NULL THEN
        RAISE NOTICE 'SKIP % %: tabla vacía', p_tabla, p_operacion;
        RETURN;
    END IF;

    BEGIN
        EXECUTE format(p_asignacion, v_id);
        RAISE EXCEPTION 'ASSERTION FAILED: % % no fue bloqueado', p_tabla, p_operacion;
    EXCEPTION
        WHEN others THEN
            IF SQLERRM NOT LIKE 'Tabla de solo-agregado:%' THEN
                RAISE;
            END IF;
            RAISE NOTICE 'OK % % bloqueado: %', p_tabla, p_operacion, SQLERRM;
    END;
END;
$$;

SELECT pg_temp.assert_solo_agregado_bloqueado(
    'historial_estado_orden', 'UPDATE',
    'UPDATE historial_estado_orden SET cuando = NOW() WHERE id = %s'
);
SELECT pg_temp.assert_solo_agregado_bloqueado(
    'historial_estado_orden', 'DELETE',
    'DELETE FROM historial_estado_orden WHERE id = %s'
);
SELECT pg_temp.assert_solo_agregado_bloqueado(
    'movimiento_stock', 'UPDATE',
    'UPDATE movimiento_stock SET cantidad = cantidad WHERE id = %s'
);
SELECT pg_temp.assert_solo_agregado_bloqueado(
    'movimiento_stock', 'DELETE',
    'DELETE FROM movimiento_stock WHERE id = %s'
);
SELECT pg_temp.assert_solo_agregado_bloqueado(
    'historial_precio_repuesto', 'UPDATE',
    'UPDATE historial_precio_repuesto SET precio_nuevo = precio_nuevo + 1 WHERE id = %s'
);
SELECT pg_temp.assert_solo_agregado_bloqueado(
    'historial_precio_repuesto', 'DELETE',
    'DELETE FROM historial_precio_repuesto WHERE id = %s'
);

DROP FUNCTION pg_temp.assert_solo_agregado_bloqueado(text, text, text);
