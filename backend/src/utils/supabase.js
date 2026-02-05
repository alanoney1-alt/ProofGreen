const { createClient } = require('@supabase/supabase-js');
const { logger } = require('./logger');

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_KEY;

if (!supabaseUrl || !supabaseServiceKey) {
  logger.warn('Supabase credentials not configured. Database operations will fail.');
}

// Service role client for backend operations
const supabase = createClient(
  supabaseUrl || 'https://placeholder.supabase.co',
  supabaseServiceKey || 'placeholder',
  {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  }
);

// Helper function to handle Supabase errors
const handleSupabaseError = (error, operation) => {
  logger.error(`Supabase ${operation} error:`, error);
  throw new Error(`Database error during ${operation}: ${error.message}`);
};

// Generic query helpers
const dbHelpers = {
  async findById(table, id) {
    const { data, error } = await supabase
      .from(table)
      .select('*')
      .eq('id', id)
      .single();

    if (error && error.code !== 'PGRST116') {
      handleSupabaseError(error, `findById in ${table}`);
    }
    return data;
  },

  async findOne(table, conditions) {
    let query = supabase.from(table).select('*');

    Object.entries(conditions).forEach(([key, value]) => {
      query = query.eq(key, value);
    });

    const { data, error } = await query.single();

    if (error && error.code !== 'PGRST116') {
      handleSupabaseError(error, `findOne in ${table}`);
    }
    return data;
  },

  async findMany(table, conditions = {}, options = {}) {
    let query = supabase.from(table).select(options.select || '*');

    Object.entries(conditions).forEach(([key, value]) => {
      query = query.eq(key, value);
    });

    if (options.orderBy) {
      query = query.order(options.orderBy, { ascending: options.ascending ?? true });
    }

    if (options.limit) {
      query = query.limit(options.limit);
    }

    const { data, error } = await query;

    if (error) {
      handleSupabaseError(error, `findMany in ${table}`);
    }
    return data || [];
  },

  async create(table, data) {
    const { data: result, error } = await supabase
      .from(table)
      .insert(data)
      .select()
      .single();

    if (error) {
      handleSupabaseError(error, `create in ${table}`);
    }
    return result;
  },

  async update(table, id, data) {
    const { data: result, error } = await supabase
      .from(table)
      .update({ ...data, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select()
      .single();

    if (error) {
      handleSupabaseError(error, `update in ${table}`);
    }
    return result;
  },

  async delete(table, id) {
    const { error } = await supabase
      .from(table)
      .delete()
      .eq('id', id);

    if (error) {
      handleSupabaseError(error, `delete in ${table}`);
    }
    return true;
  }
};

module.exports = { supabase, dbHelpers, handleSupabaseError };
