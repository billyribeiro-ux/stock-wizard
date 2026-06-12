/**
 * Same-origin proxy for discovery exports.
 *
 * The browser can never talk to FastAPI directly (internal token, private base
 * URL), so the page's "Download CSV / PDF" links point here and this handler
 * streams the export through the server-only api client.
 */
import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exportDiscovery } from '$lib/server/api';

export const GET: RequestHandler = async ({ params, url }) => {
	const fmt = url.searchParams.get('fmt') ?? 'csv';
	if (fmt !== 'csv' && fmt !== 'pdf') {
		error(400, { message: `Unsupported export format "${fmt}" (use csv or pdf)` });
	}

	const upstream = await exportDiscovery(params.id, fmt);
	if (!upstream.ok) {
		let detail = upstream.statusText;
		try {
			const payload = (await upstream.json()) as { detail?: string; message?: string };
			detail = payload.detail ?? payload.message ?? detail;
		} catch {
			// non-JSON error body; keep the status text
		}
		error(upstream.status, { message: detail || `Export failed (${upstream.status})` });
	}

	const contentType =
		upstream.headers.get('content-type') ?? (fmt === 'pdf' ? 'application/pdf' : 'text/csv');
	const disposition =
		upstream.headers.get('content-disposition') ??
		`attachment; filename="discovery-${params.id}.${fmt}"`;

	return new Response(upstream.body, {
		status: 200,
		headers: {
			'content-type': contentType,
			'content-disposition': disposition
		}
	});
};
