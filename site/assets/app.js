const myIpEl = document.getElementById("my-ip");
const myIpMetaEl = document.getElementById("my-ip-meta");
const ipResultEl = document.getElementById("ip-result");
const dnsResultEl = document.getElementById("dns-result");
const domainResultEl = document.getElementById("domain-result");
const passwordOutputEl = document.getElementById("password-output");
const uuidOutputEl = document.getElementById("uuid-output");

async function fetchJson(url) {
	const res = await fetch(url, { headers: { Accept: "application/json" } });
	if (!res.ok) {
		throw new Error(`HTTP ${res.status}`);
	}
	return res.json();
}

function asPrettyJson(data) {
	return JSON.stringify(data, null, 2);
}

function metaItem(label, value) {
	const wrapper = document.createElement("div");
	wrapper.className = "meta-item";

	const labelEl = document.createElement("div");
	labelEl.className = "label";
	labelEl.textContent = label;

	const valueEl = document.createElement("div");
	valueEl.className = "value";
	valueEl.textContent = value || "-";

	wrapper.append(labelEl, valueEl);
	return wrapper;
}

async function loadMyIp() {
	myIpEl.textContent = "Loading...";
	myIpMetaEl.innerHTML = "";
	try {
		const data = await fetchJson("https://ipapi.co/json/");
		myIpEl.textContent = data.ip || "Unknown";
		myIpMetaEl.append(
			metaItem("Country", data.country_name),
			metaItem("City", data.city),
			metaItem("ASN", data.asn),
			metaItem("Org", data.org)
		);
	} catch (err) {
		myIpEl.textContent = "Unavailable";
		myIpMetaEl.append(metaItem("Error", String(err.message || err)));
	}
}

async function lookupIp(ip) {
	ipResultEl.textContent = "Loading...";
	try {
		const data = await fetchJson(`https://ipapi.co/${encodeURIComponent(ip)}/json/`);
		ipResultEl.textContent = asPrettyJson(data);
	} catch (err) {
		ipResultEl.textContent = `Lookup failed: ${err.message || err}`;
	}
}

async function lookupDns(domain, type) {
	dnsResultEl.textContent = "Resolving...";
	try {
		const data = await fetchJson(`https://dns.google/resolve?name=${encodeURIComponent(domain)}&type=${encodeURIComponent(type)}`);
		const answer = data.Answer || [];
		dnsResultEl.textContent = answer.length
			? asPrettyJson(answer)
			: asPrettyJson({ Status: data.Status, message: "No records returned" });
	} catch (err) {
		dnsResultEl.textContent = `DNS lookup failed: ${err.message || err}`;
	}
}

async function domainProfile(domain) {
	domainResultEl.textContent = "Checking...";
	try {
		const rdap = await fetchJson(`https://rdap.org/domain/${encodeURIComponent(domain)}`);
		const profile = {
			ldHName: rdap.ldhName,
			handle: rdap.handle,
			status: rdap.status,
			nameservers: (rdap.nameservers || []).map((n) => n.ldhName),
			events: (rdap.events || []).map((e) => ({ action: e.eventAction, date: e.eventDate })),
		};
		domainResultEl.textContent = asPrettyJson(profile);
	} catch (err) {
		domainResultEl.textContent = `Domain check failed: ${err.message || err}`;
	}
}

function generatePassword(length) {
	const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*";
	const array = new Uint32Array(length);
	crypto.getRandomValues(array);
	let out = "";
	for (let i = 0; i < length; i += 1) {
		out += chars[array[i] % chars.length];
	}
	return out;
}

function generateUuid() {
	if (crypto.randomUUID) {
		return crypto.randomUUID();
	}
	const bytes = new Uint8Array(16);
	crypto.getRandomValues(bytes);
	bytes[6] = (bytes[6] & 0x0f) | 0x40;
	bytes[8] = (bytes[8] & 0x3f) | 0x80;
	const toHex = (n) => n.toString(16).padStart(2, "0");
	const hex = Array.from(bytes, toHex).join("");
	return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function copyText(text) {
	if (!text || text === "-") {
		return;
	}
	await navigator.clipboard.writeText(text);
}

function bindEvents() {
	document.getElementById("refresh-ip").addEventListener("click", loadMyIp);

	document.getElementById("ip-lookup-form").addEventListener("submit", (e) => {
		e.preventDefault();
		const ip = new FormData(e.currentTarget).get("ip");
		lookupIp(String(ip || "").trim());
	});

	document.getElementById("dns-form").addEventListener("submit", (e) => {
		e.preventDefault();
		const data = new FormData(e.currentTarget);
		const domain = String(data.get("domain") || "").trim();
		const type = String(data.get("type") || "A");
		lookupDns(domain, type);
	});

	document.getElementById("domain-form").addEventListener("submit", (e) => {
		e.preventDefault();
		const domain = new FormData(e.currentTarget).get("domain");
		domainProfile(String(domain || "").trim());
	});

	document.getElementById("generate-password").addEventListener("click", () => {
		const length = Number(document.getElementById("password-length").value) || 18;
		passwordOutputEl.textContent = generatePassword(Math.max(8, Math.min(length, 64)));
	});

	document.getElementById("generate-uuid").addEventListener("click", () => {
		uuidOutputEl.textContent = generateUuid();
	});

	document.getElementById("copy-password").addEventListener("click", async () => {
		await copyText(passwordOutputEl.textContent);
	});

	document.getElementById("copy-uuid").addEventListener("click", async () => {
		await copyText(uuidOutputEl.textContent);
	});
}

function setupReveal() {
	const observer = new IntersectionObserver(
		(entries) => {
			entries.forEach((entry) => {
				if (entry.isIntersecting) {
					entry.target.classList.add("is-visible");
				}
			});
		},
		{ threshold: 0.12 }
	);
	document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));
}

bindEvents();
setupReveal();
loadMyIp();
