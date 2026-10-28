CREATE TABLE etiquetas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE imagenes (
    id SERIAL PRIMARY KEY,
    id_externo INT NOT NULL UNIQUE,

    file_name VARCHAR(255) NOT NULL,
    split VARCHAR(10) NOT NULL CHECK (split IN ('train', 'test', 'val')),

    ruta_imagen TEXT NOT NULL,
    ruta_thumbnail TEXT,

    width INT NOT NULL,
    height INT NOT NULL,
    file_size_kb REAL,

    numero_instancias INT NOT NULL DEFAULT 0,
    numero_categorias INT NOT NULL DEFAULT 0,

    angulo_fotografia VARCHAR(50),
    cobertura VARCHAR(50),
    color_vehiculo VARCHAR(50),
    observaciones TEXT
);

CREATE TABLE instancias (
    id SERIAL PRIMARY KEY,

    imagen_id INT NOT NULL,
    categoria_id INT NOT NULL,

    segmentacion JSONB NOT NULL,

    area REAL NOT NULL CHECK (area >= 0),
    area_pct DOUBLE PRECISION NOT NULL CHECK (area_pct >= 0 AND area_pct <= 100),

    bbox_x REAL NOT NULL,
    bbox_y REAL NOT NULL,
    bbox_width REAL NOT NULL CHECK (bbox_width >= 0),
    bbox_height REAL NOT NULL CHECK (bbox_height >= 0),

    FOREIGN KEY (imagen_id) REFERENCES imagenes(id) ON DELETE CASCADE,
    FOREIGN KEY (categoria_id) REFERENCES etiquetas(id) ON DELETE RESTRICT
);

CREATE INDEX idx_imagenes_split ON imagenes(split);
CREATE INDEX idx_imagenes_color ON imagenes(color_vehiculo);
CREATE INDEX idx_imagenes_angulo ON imagenes(angulo_fotografia);
CREATE INDEX idx_imagenes_cobertura ON imagenes(cobertura);
CREATE INDEX idx_imagenes_num_instancias ON imagenes(numero_instancias);
CREATE INDEX idx_imagenes_num_categorias ON imagenes(numero_categorias);

CREATE INDEX idx_instancias_imagen_id ON instancias(imagen_id);
CREATE INDEX idx_instancias_categoria_id ON instancias(categoria_id);
CREATE INDEX idx_instancias_area ON instancias(area);
CREATE INDEX idx_instancias_area_pct ON instancias(area_pct);