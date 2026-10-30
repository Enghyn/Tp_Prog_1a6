-- test/seed.sql
-- Espejo manual e idempotente de `seed.py` para PostgreSQL.
--
-- Uso:
--   psql "$DATABASE_URL" -f test/seed.sql
--
-- Es seguro ejecutarlo varias veces: usa `ON CONFLICT DO NOTHING` y
-- `INSERT ... WHERE NOT EXISTS`. No hace `UPDATE` ni `DELETE`, por lo que
-- convive con los triggers de solo-agregado (RN-15). La única excepción es
-- `estado_orden`, catálogo que converge a sus valores canónicos (RN-19).
--
-- Los hashes bcrypt están congelados y corresponden a las credenciales de
-- desarrollo documentadas en README.md. NO usar en producción.

BEGIN;

-- ---------------------------------------------------------------------------
-- Catálogo canónico de estados (RN-19)
-- ---------------------------------------------------------------------------
INSERT INTO estado_orden (codigo, descripcion, posicion, es_final)
VALUES
    ('PENDIENTE', 'Pendiente de inicio', 1, false),
    ('EN_REPARACION', 'En reparación', 2, false),
    ('TERMINADA', 'Terminada', 3, true),
    ('CANCELADA', 'Cancelada', 4, true)
ON CONFLICT (codigo) DO UPDATE
SET descripcion = EXCLUDED.descripcion,
    posicion = EXCLUDED.posicion,
    es_final = EXCLUDED.es_final;

-- ---------------------------------------------------------------------------
-- Usuarios base (contraseñas de desarrollo)
-- ---------------------------------------------------------------------------
INSERT INTO usuario (
    email, nombre, password_hash, activo,
    debe_cambiar_password, password_cambiada_en
)
VALUES
    (
        'admin@taller.local',
        'Administrador del Sistema',
        '$2b$12$0oDZOMRTGA4sxmVREpgBMumAvGZPGLQWYlfQJgtln/wd/M6qiSJSa',
        true, false, NULL
    ),
    (
        'recepcion@taller.local',
        'Recepción del Taller',
        '$2b$12$vrRGcl1M0k6qhB70jYwW3./NrPo8m109ssPKk.qkWQuwB2H544orO',
        true, false, NULL
    ),
    (
        'mecanico@taller.local',
        'Mecánico del Taller',
        '$2b$12$kBOLudvcuWU9OK.M.8ikaeR5kjKRlc9LU6h015gDtXIfWNJw7gRsG',
        true, true, NULL
    ),
    (
        'cliente@taller.local',
        'Cliente Demo',
        '$2b$12$zp7NzWPYiXiWYV4K8jxnOORNJdpm5AVc3nYmk.4qI14.E6NdPboxq',
        true, false, NULL
    )
ON CONFLICT (email) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Asignaciones de rol abiertas (una por usuario)
-- ---------------------------------------------------------------------------
INSERT INTO asignacion_rol (
    usuario_id, rol, desde, vence_en, revocada_en, otorgada_por
)
SELECT
    u.id,
    v.rol,
    '2026-01-02 08:00:00+00'::timestamptz,
    NULL,
    NULL,
    CASE
        WHEN v.rol = 'ADMIN' THEN NULL
        ELSE (SELECT id FROM usuario WHERE email = 'admin@taller.local')
    END
FROM (
    VALUES
        ('admin@taller.local', 'ADMIN'),
        ('recepcion@taller.local', 'RECEPCION'),
        ('mecanico@taller.local', 'MECANICO'),
        ('cliente@taller.local', 'CLIENTE')
) AS v(email, rol)
JOIN usuario u ON u.email = v.email
WHERE NOT EXISTS (
    SELECT 1
    FROM asignacion_rol a
    WHERE a.usuario_id = u.id
      AND a.rol = v.rol
      AND a.revocada_en IS NULL
);

-- ---------------------------------------------------------------------------
-- Clientes y vehículos
-- ---------------------------------------------------------------------------
INSERT INTO cliente (usuario_id, nombre, documento, telefono)
VALUES
    (
        (SELECT id FROM usuario WHERE email = 'cliente@taller.local'),
        'Cliente Demo Uno', '30111222', '1144440001'
    ),
    (NULL, 'Cliente Demo Dos', '30999888', '1144440002')
ON CONFLICT (documento) DO NOTHING;

INSERT INTO vehiculo (cliente_id, patente, marca, modelo, anio, borrado_en)
SELECT c.id, v.patente, v.marca, v.modelo, v.anio, NULL
FROM (
    VALUES
        ('30111222', 'AB123CD', 'Toyota', 'Corolla', 2020),
        ('30111222', 'AC456EF', 'Ford', 'Ranger', 2018),
        ('30999888', 'AD789GH', 'Volkswagen', 'Gol', 2015)
) AS v(documento, patente, marca, modelo, anio)
JOIN cliente c ON c.documento = v.documento
ON CONFLICT (patente) WHERE borrado_en IS NULL DO NOTHING;

-- ---------------------------------------------------------------------------
-- Repuestos y movimientos de alta (RN-14)
-- ---------------------------------------------------------------------------
INSERT INTO repuesto (codigo, descripcion, precio, stock, borrado_en)
VALUES
    ('FIL-001', 'Filtro de aceite', 15000.00, 10, NULL),
    ('ACE-001', 'Aceite sintético 5W-30', 12000.00, 20, NULL),
    ('BAT-001', 'Batería 12V 60Ah', 85000.00, 5, NULL),
    ('PAS-001', 'Pastillas de freno delanteras', 45000.00, 8, NULL)
ON CONFLICT (codigo) WHERE borrado_en IS NULL DO NOTHING;

INSERT INTO movimiento_stock (
    repuesto_id, orden_id, usuario_id, cantidad, motivo, cuando
)
SELECT
    r.id,
    NULL,
    (SELECT id FROM usuario WHERE email = 'admin@taller.local'),
    v.cantidad,
    'ALTA',
    '2026-01-02 09:00:00+00'::timestamptz
FROM (
    VALUES
        ('FIL-001', 10),
        ('ACE-001', 20),
        ('BAT-001', 6),
        ('PAS-001', 8)
) AS v(codigo, cantidad)
JOIN repuesto r ON r.codigo = v.codigo AND r.borrado_en IS NULL
WHERE NOT EXISTS (
    SELECT 1
    FROM movimiento_stock m
    WHERE m.repuesto_id = r.id
      AND m.motivo = 'ALTA'
      AND m.cantidad = v.cantidad
      AND m.cuando = '2026-01-02 09:00:00+00'::timestamptz
);

-- ---------------------------------------------------------------------------
-- Órdenes demo
-- ---------------------------------------------------------------------------
INSERT INTO orden_trabajo (
    vehiculo_id, mecanico_id, estado, falla, creada_en, total
)
SELECT
    vh.id,
    v.mecanico_id,
    v.estado,
    v.falla,
    v.creada_en,
    v.total
FROM (
    VALUES
        (
            'AB123CD', NULL::integer, 'PENDIENTE',
            '[demo] Ruido en tren delantero',
            '2026-01-05 09:00:00+00'::timestamptz, 90000.00::numeric(12, 2)
        ),
        (
            'AC456EF',
            (SELECT id FROM usuario WHERE email = 'mecanico@taller.local'),
            'EN_REPARACION',
            '[demo] Service completo',
            '2026-01-06 10:00:00+00'::timestamptz, 39000.00::numeric(12, 2)
        ),
        (
            'AD789GH',
            (SELECT id FROM usuario WHERE email = 'mecanico@taller.local'),
            'TERMINADA',
            '[demo] Batería agotada',
            '2026-01-07 11:00:00+00'::timestamptz, 85000.00::numeric(12, 2)
        )
) AS v(patente, mecanico_id, estado, falla, creada_en, total)
JOIN vehiculo vh ON vh.patente = v.patente AND vh.borrado_en IS NULL
WHERE NOT EXISTS (
    SELECT 1
    FROM orden_trabajo o
    WHERE o.vehiculo_id = vh.id
      AND o.falla = v.falla
);

-- ---------------------------------------------------------------------------
-- Ítems de las órdenes (precio copiado del repuesto)
-- ---------------------------------------------------------------------------
INSERT INTO item_orden (orden_id, repuesto_id, cantidad, precio_unitario)
SELECT o.id, r.id, v.cantidad, v.precio
FROM (
    VALUES
        ('[demo] Ruido en tren delantero', 'PAS-001', 2, 45000.00::numeric(10, 2)),
        ('[demo] Service completo', 'FIL-001', 1, 15000.00::numeric(10, 2)),
        ('[demo] Service completo', 'ACE-001', 2, 12000.00::numeric(10, 2)),
        ('[demo] Batería agotada', 'BAT-001', 1, 85000.00::numeric(10, 2))
) AS v(falla, codigo, cantidad, precio)
JOIN orden_trabajo o ON o.falla = v.falla
JOIN repuesto r ON r.codigo = v.codigo AND r.borrado_en IS NULL
ON CONFLICT (orden_id, repuesto_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Historial de estados (desde NULL, sin saltos)
-- ---------------------------------------------------------------------------
INSERT INTO historial_estado_orden (
    orden_id, desde_estado, hasta_estado, usuario_id, cuando
)
SELECT
    o.id,
    v.desde_estado,
    v.hasta_estado,
    (SELECT id FROM usuario WHERE email = v.email_usuario),
    v.cuando
FROM (
    VALUES
        (
            '[demo] Ruido en tren delantero', NULL::text, 'PENDIENTE',
            'recepcion@taller.local', '2026-01-05 09:00:00+00'::timestamptz
        ),
        (
            '[demo] Service completo', NULL::text, 'PENDIENTE',
            'recepcion@taller.local', '2026-01-06 10:00:00+00'::timestamptz
        ),
        (
            '[demo] Service completo', 'PENDIENTE', 'EN_REPARACION',
            'mecanico@taller.local', '2026-01-06 11:00:00+00'::timestamptz
        ),
        (
            '[demo] Batería agotada', NULL::text, 'PENDIENTE',
            'recepcion@taller.local', '2026-01-07 11:00:00+00'::timestamptz
        ),
        (
            '[demo] Batería agotada', 'PENDIENTE', 'EN_REPARACION',
            'mecanico@taller.local', '2026-01-07 12:00:00+00'::timestamptz
        ),
        (
            '[demo] Batería agotada', 'EN_REPARACION', 'TERMINADA',
            'mecanico@taller.local', '2026-01-07 15:00:00+00'::timestamptz
        )
) AS v(falla, desde_estado, hasta_estado, email_usuario, cuando)
JOIN orden_trabajo o ON o.falla = v.falla
WHERE NOT EXISTS (
    SELECT 1
    FROM historial_estado_orden h
    WHERE h.orden_id = o.id
      AND h.desde_estado IS NOT DISTINCT FROM v.desde_estado
      AND h.hasta_estado = v.hasta_estado
      AND h.cuando = v.cuando
);

-- ---------------------------------------------------------------------------
-- Consumo de la orden TERMINADA: BAT-001 -1
-- ---------------------------------------------------------------------------
INSERT INTO movimiento_stock (
    repuesto_id, orden_id, usuario_id, cantidad, motivo, cuando
)
SELECT
    r.id,
    o.id,
    (SELECT id FROM usuario WHERE email = 'mecanico@taller.local'),
    -1,
    'TERMINACION',
    '2026-01-07 15:00:00+00'::timestamptz
FROM repuesto r
JOIN orden_trabajo o ON o.falla = '[demo] Batería agotada'
WHERE r.codigo = 'BAT-001'
  AND r.borrado_en IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM movimiento_stock m
      WHERE m.repuesto_id = r.id
        AND m.motivo = 'TERMINACION'
        AND m.cantidad = -1
        AND m.cuando = '2026-01-07 15:00:00+00'::timestamptz
  );

-- ---------------------------------------------------------------------------
-- Evento de auditoría único
-- ---------------------------------------------------------------------------
INSERT INTO evento_seguridad (cuando, actor, accion)
SELECT '2026-01-08 00:00:00+00'::timestamptz, 'SISTEMA', 'seed_inicial'
WHERE NOT EXISTS (
    SELECT 1
    FROM evento_seguridad
    WHERE actor = 'SISTEMA'
      AND accion = 'seed_inicial'
);

COMMIT;
