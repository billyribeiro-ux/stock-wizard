import * as v from 'valibot';
import { query, command, form } from '$app/server';
import * as api from '$lib/server/api';
import type { Vendor } from '$lib/types';

/** Configured vendor API keys (masked). */
export const listVendors = query(async (): Promise<Vendor[]> => {
	return api.listVendors();
});

const AddKeySchema = v.object({
	vendor: v.pipe(v.string(), v.nonEmpty('Vendor is required')),
	label: v.pipe(v.string(), v.nonEmpty('Give the key a label')),
	// leading underscore => never sent back to the browser on validation failure
	_api_key: v.pipe(v.string(), v.nonEmpty('API key is required')),
	scopes: v.optional(v.array(v.string()), [])
});

/**
 * Add a vendor key via a progressively-enhanced form. Because this is a `form`
 * remote function, the plaintext `_api_key` is submitted directly to the server
 * and never lives in the client bundle. On success the vendor list is
 * refreshed in the same flight.
 */
export const addVendorKey = form(AddKeySchema, async ({ vendor, label, _api_key, scopes }) => {
	const { id } = await api.createVendorKey({
		vendor,
		label,
		api_key: _api_key,
		scopes: scopes ?? []
	});

	// single-flight: refresh the masked vendor list alongside the response
	void listVendors().refresh();

	return { id, success: true as const };
});

const ToggleSchema = v.object({
	id: v.pipe(v.string(), v.nonEmpty()),
	enabled: v.boolean()
});

/** Enable or disable a stored key. */
export const setVendorEnabled = command(ToggleSchema, async ({ id, enabled }) => {
	const result = await api.setVendorKeyEnabled(id, enabled);
	void listVendors().refresh();
	return result;
});

/** Remove a stored key entirely. */
export const removeVendorKey = command(
	v.pipe(v.string(), v.nonEmpty()),
	async (id): Promise<{ id: string }> => {
		await api.deleteVendorKey(id);
		void listVendors().refresh();
		return { id };
	}
);
