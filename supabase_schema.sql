-- Supermarket Price Comparison Schema

-- Enable necessary extensions if needed (e.g., for vector search later, not needed now)

-- 1. Chains
CREATE TABLE IF NOT EXISTS chains (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL, -- Enum identifier (e.g., 'SHUFERSAL', 'RamiLevy')
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Stores
CREATE TABLE IF NOT EXISTS stores (
    id SERIAL PRIMARY KEY,
    chain_id INTEGER REFERENCES chains(id) ON DELETE CASCADE,
    store_id_in_chain TEXT NOT NULL, -- The ID collected from the XML
    name TEXT,
    city TEXT,
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(chain_id, store_id_in_chain)
);

-- 3. Products
CREATE TABLE IF NOT EXISTS products (
    id BIGSERIAL PRIMARY KEY,
    chain_id INTEGER REFERENCES chains(id) ON DELETE CASCADE,
    product_code TEXT NOT NULL, -- Barcode or Internal ID
    name TEXT NOT NULL,
    manufacturer_name TEXT,
    unit_of_measure TEXT,
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(chain_id, product_code)
);

-- 4. Prices
CREATE TABLE IF NOT EXISTS prices (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    store_id INTEGER REFERENCES stores(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL,
    price_update_date TIMESTAMP WITH TIME ZONE NOT NULL,
    is_promotion BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(product_id, store_id) -- One price per product per store
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_code ON products(product_code);
CREATE INDEX IF NOT EXISTS idx_prices_store ON prices(store_id);
