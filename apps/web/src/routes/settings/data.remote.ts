import * as v from 'valibot';
import { query, command, form } from '$app/server';
import * as api from '$lib/server/api';
import type { Vendor, VendorCatalogEntry } from '$lib/types';

/** Supported vendors and their capabilities (for the add-key picker). */
export const listVendorCatalog = query(async (): Promise<VendorCatalogEntry[]> => {
	return api.listVendorCatalog();
});

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

const RotateSchema = v.object({
	id: v.pipe(v.string(), v.nonEmpty()),
	// leading underscore => the plaintext secret is never sent back to the browser
	_api_key: v.pipe(v.string(), v.nonEmpty('New API key is required'))
});

/**
 * Rotate (replace in place) a stored key's secret via a progressively-enhanced
 * form, so the plaintext never lives in the client bundle. Use `.for(id)` per
 * row to isolate instances. Refreshes the masked list in the same flight.
 */
export const rotateVendorKey = form(RotateSchema, async ({ id, _api_key }) => {
	const result = await api.rotateVendorKey(id, _api_key);
	void listVendors().refresh();
	return { ...result, success: true as const };
});

const RenameSchema = v.object({
	id: v.pipe(v.string(), v.nonEmpty()),
	label: v.pipe(v.string(), v.nonEmpty('Label is required'))
});

/** Rename a stored key's display label. */
export const renameVendorKey = command(RenameSchema, async ({ id, label }) => {
	const result = await api.renameVendorKey(id, label);
	void listVendors().refresh();
	return result;
});

const ToggleSchema = v.object({
	id: v.pipe(v.string(), v.nonEmpty()),
	enabled: v.boolean()
});

/** Enable or disable a stored key ("swap" the active key for a vendor). */
export const setVendorEnabled = command(ToggleSchema, async ({ id, enabled }) => {
	const result = await api.setVendorKeyEnabled(id, enabled);
	void listVendors().refresh();
	return result;
});

// --- Charles Schwab OAuth2 (3-legged) ---------------------------------------

const SchwabConnectSchema = v.object({
	// leading underscores => secrets never returned to the browser on validation failure
	_app_key: v.pipe(v.string(), v.nonEmpty('App key is required')),
	_app_secret: v.pipe(v.string(), v.nonEmpty('App secret is required')),
	redirect_uri: v.pipe(v.string(), v.nonEmpty('Redirect URI is required')),
	label: v.optional(v.string(), 'Charles Schwab')
});

/**
 * Step 1 of the Schwab OAuth flow: store the app key/secret bundle (encrypted,
 * disabled) and return the authorize URL the user opens to consent. Submitted as
 * a `form` so the app secret never lives in the client bundle.
 */
export const connectSchwab = form(
	SchwabConnectSchema,
	async ({ _app_key, _app_secret, redirect_uri, label }) => {
		const result = await api.schwabConnect({
			app_key: _app_key,
			app_secret: _app_secret,
			redirect_uri,
			label: label || 'Charles Schwab'
		});
		void listVendors().refresh();
		return { ...result, success: true as const };
	}
);

const SchwabTokenSchema = v.object({
	key_id: v.pipe(v.string(), v.nonEmpty('Connect first to get a credential id')),
	// the returned redirect URL (contains ?code=…) pasted back by the user
	redirect_url: v.pipe(v.string(), v.nonEmpty('Paste the full URL Schwab redirected you to'))
});

/**
 * Step 2: exchange the authorization code (extracted from the pasted redirect
 * URL) for access + refresh tokens, then enable the key for scans.
 */
export const exchangeSchwabCode = form(SchwabTokenSchema, async ({ key_id, redirect_url }) => {
	const result = await api.schwabExchange({ key_id, redirect_url });
	void listVendors().refresh();
	return { ...result, success: true as const };
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
