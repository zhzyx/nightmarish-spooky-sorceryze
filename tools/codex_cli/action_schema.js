'use strict';

// JSON strings cannot constrain their decoded contents. Use typed arguments
// where the host supplies a closed schema, and keep dynamic tools on the legacy
// encoding. Only the host executes tools, after the complete batch is checked.
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const acceptsNull = schema => !schema?.type || schema.type === 'null'
    || Array.isArray(schema.type) && schema.type.includes('null');

function strictSchema(schema) {
    if (!object(schema) || typeof schema.type !== 'string'
        || !['object', 'array', 'string', 'number', 'integer', 'boolean', 'null'].includes(schema.type)
        || schema.anyOf || schema.oneOf || schema.$ref) return null;
    const result = { ...schema };
    if (schema.type === 'object') {
        if (!object(schema.properties) || schema.additionalProperties !== false) return null;
        const required = new Set(schema.required || []);
        result.properties = {};
        for (const [key, child] of Object.entries(schema.properties)) {
            const normalized = strictSchema(child);
            if (!normalized) return null;
            result.properties[key] = required.has(key) ? normalized : { anyOf: [normalized, { type: 'null' }] };
        }
        result.required = Object.keys(schema.properties);
    } else if (schema.type === 'array') {
        result.items = strictSchema(schema.items);
        if (!result.items) return null;
    }
    return result;
}

function outputSchemaFor(input, base) {
    const variants = input.available_tools.map(({ function: tool }) => ({
        type: 'object', additionalProperties: false, required: ['name', 'arguments'],
        properties: {
            name: { type: 'string', enum: [tool.name] },
            arguments: strictSchema(tool.parameters) || { type: 'string' },
        },
    }));
    return { ...base, properties: { ...base.properties, actions: {
        type: 'array', maxItems: variants.length ? 32 : 0,
        items: variants.length === 1 ? variants[0] : variants.length ? { anyOf: variants } : base.properties.actions.items,
    } } };
}

function check(value, schema) {
    if (!object(schema)) return;
    const types = Array.isArray(schema.type) ? schema.type : schema.type ? [schema.type] : [];
    const matches = type => type === 'object' ? object(value) : type === 'array' ? Array.isArray(value)
        : type === 'null' ? value === null : type === 'integer' ? Number.isSafeInteger(value)
        : type === 'number' ? typeof value === 'number' && Number.isFinite(value) : typeof value === type;
    if (types.length && !types.some(matches)) throw new Error('argument_type');
    if (schema.enum && !schema.enum.some(item => JSON.stringify(item) === JSON.stringify(value))) throw new Error('argument_enum');
    if (object(value)) {
        for (const key of schema.required || []) if (!Object.hasOwn(value, key)) throw new Error('argument_required');
        for (const [key, child] of Object.entries(value)) {
            if (schema.additionalProperties === false && !Object.hasOwn(schema.properties || {}, key)) throw new Error('argument_extra');
            check(child, schema.properties?.[key]);
        }
    }
    if (Array.isArray(value)) {
        if (schema.maxItems !== undefined && value.length > schema.maxItems) throw new Error('argument_range');
        for (const child of value) check(child, schema.items);
    }
    if (typeof value === 'number' && (schema.minimum !== undefined && value < schema.minimum
        || schema.maximum !== undefined && value > schema.maximum)) throw new Error('argument_range');
}

function omitPlaceholders(value, schema) {
    if (Array.isArray(value)) return value.map(child => omitPlaceholders(child, schema.items));
    if (!object(value)) return value;
    const required = new Set(schema.required || []);
    const pairs = Object.entries(value).filter(([key, child]) => child !== null || required.has(key)
        || !Object.hasOwn(schema.properties || {}, key) || acceptsNull(schema.properties[key]));
    return Object.fromEntries(pairs.map(([key, child]) => [key,
        schema.properties?.[key] ? omitPlaceholders(child, schema.properties[key]) : child]));
}

function argumentsForHost(raw, parameters) {
    const legacy = typeof raw === 'string';
    let args;
    try { args = legacy ? JSON.parse(raw) : raw; } catch (_) { throw new Error('argument_json'); }
    if (!object(args)) throw new Error('argument_object');
    if (!legacy && strictSchema(parameters)) args = omitPlaceholders(args, parameters);
    check(args, parameters);
    return args;
}

module.exports = { outputSchemaFor, argumentsForHost };
