const PART_TYPE_ORDER = ["MMIC", "DIODE", "CIRCUIT", "PCB", "FILTER", "NA", "MISC", "CONNECTOR"];
const NOTE_TYPE_ORDER = ["REWORK_SUMMARY", "CURRENT_TEST", "PCB_DEVIATIONS", "INDIUM", "TEMPERATURE", "GENERIC"];
const ILLEGAL_FILENAME_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*'];

function sortPartsContainer() {
	const container = document.getElementById("actual-parts-container");
	const rows = Array.from(container.querySelectorAll(".part-row"));
	rows.sort((a, b) => {
		const typeA = a.querySelector("select[name='part_type']").value;
		const typeB = b.querySelector("select[name='part_type']").value;
		const indexA = PART_TYPE_ORDER.includes(typeA) ? PART_TYPE_ORDER.indexOf(typeA) : 99;
		const indexB = PART_TYPE_ORDER.includes(typeB) ? PART_TYPE_ORDER.indexOf(typeB) : 99;
		return indexA - indexB;
	});
	rows.forEach(row => container.appendChild(row));
}

function sortNotesContainer() {
	const container = document.getElementById("actual-notes-container");
	const rows = Array.from(container.querySelectorAll(".note-row"));
	rows.sort((a, b) => {
		const typeA = a.querySelector("select[name='note_type']").value;
		const typeB = b.querySelector("select[name='note_type']").value;
		const indexA = NOTE_TYPE_ORDER.includes(typeA) ? NOTE_TYPE_ORDER.indexOf(typeA) : 99;
		const indexB = NOTE_TYPE_ORDER.includes(typeB) ? NOTE_TYPE_ORDER.indexOf(typeB) : 99;
		return indexA - indexB;
	});
	rows.forEach(row => container.appendChild(row));
}


function sanitizeInput(input, restrictedChars, upperCase) {
	const escaped = restrictedChars.map(c => c.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, '\\$&'));
	const stripPattern = new RegExp(`[${escaped.join('')}]`, 'g');
	let val = input.value.replace(stripPattern, '');
	if (upperCase) {
		val = val.toUpperCase();
	}
	input.value = val;
}

function toggleDiodeRow(selectedElem) {
	const partRow = selectedElem.closest('.part-row');
	const diodeRow = partRow.querySelector('.diode-row');
	if (!diodeRow) return;

	const isDiode = selectedElem.value === 'DIODE';
	diodeRow.style.display = isDiode ? '' : 'none';

	// prevent hidden diode fields from being submitted
	diodeRow.querySelectorAll('input, select, textarea').forEach(elem => {
		elem.disabled = !isDiode;
	});
}

function togglePcbRow(selectedElem) {
	const partRow = selectedElem.closest('.part-row');
	const pcbRow = partRow.querySelector('.pcb-row');
	if (!pcbRow) return;

	const isPcb = selectedElem.value === 'PCB';
	pcbRow.style.display = isPcb ? '' : 'none';

	// prevent hidden diode fields from being submitted
	pcbRow.querySelectorAll('input, select, textarea').forEach(elem => {
		elem.disabled = !isPcb;
	});
}

function toggleDefaultLotByPartType(selectedPartType) {
	const partRow = selectedPartType.closest('.part-row');
	const lotSelect = partRow.querySelector('.lot-select')

	if (partRow.dataset.hasExistingLot === "true") return;
	if (!lotSelect) return;

	if (selectedPartType.value === "CONNECTOR" || selectedPartType.value === "MISC") {
		lotSelect.value = "NA";
	}
	else {
		lotSelect.value = "Choose";
	}
}

document.addEventListener("DOMContentLoaded", () => {
	document.body.addEventListener("change", (e) => {
		const select = e.target.closest("select[name='part_type']");
		if (!select) return;
		select.closest(".part-row").dataset.hasExistingLot = "false";
		sortPartsContainer();
		toggleDiodeRow(select);
		togglePcbRow(select);
		toggleDefaultLotByPartType(select);
	});

	document.body.addEventListener("htmx:afterSettle", (evt) => {
		const root = evt.target;

		// Case 1: a whole new part-row (or several) landed
		const partTypeSelects = root.matches?.("select[name='part_type']")
			? [root]
			: root.querySelectorAll("select[name='part_type']");
		partTypeSelects.forEach((select) => {
			toggleDiodeRow(select);
			togglePcbRow(select);
			toggleDefaultLotByPartType(select);
		});

		// Case 2: just the lot-container was swapped in later (search_part_lots response)
		if (root.matches?.(".lot-container") || root.closest?.(".lot-container")) {
			const partRow = root.closest(".part-row");
			const partTypeSelect = partRow?.querySelector("select[name='part_type']");
			if (partTypeSelect) toggleDefaultLotByPartType(partTypeSelect);
		}

		sortPartsContainer();
	});
});
