const PART_TYPE_ORDER = ["MMIC", "DIODE", "PCB", "CIRCUIT", "FILTER MESH", "VAC",
						 "MA PARTS", "MISC", "CONNECTOR", "BCMESH", "SP OTHER",
						"FILTER", "CABLE", "INVENTORY", "PMP", "NA"];
const NOTE_TYPE_ORDER = ["REWORK_SUMMARY", "CURRENT_TEST", "FAST_CART_NUMBER", "CAPA_NUMBER", "JOB_NUMBER", "GENERIC"];
const ILLEGAL_FILENAME_CHARACTERS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*'];
const PART_TYPES_WITH_UNIMPORTANT_LOTS = ["MISC", "CONNECTOR"];

function sortPartsContainer() {
	const container = document.getElementById("actual-parts-container");
	const rows = Array.from(container.querySelectorAll(".part-row"));
	const sorted = [...rows].sort((a, b) => {
		const typeA = a.querySelector("select[name='part_type']").value;
		const typeB = b.querySelector("select[name='part_type']").value;
		const indexA = PART_TYPE_ORDER.includes(typeA) ? PART_TYPE_ORDER.indexOf(typeA) : 99;
		const indexB = PART_TYPE_ORDER.includes(typeB) ? PART_TYPE_ORDER.indexOf(typeB) : 99;
		return indexA - indexB;
	});

	// bail out entirely if nothing needs to move — avoids
	// needless reparenting that can retrigger `revealed` hx-triggers
	const alreadySorted = sorted.every((row, i) => row === rows[i]);
	if (alreadySorted) return;

	sorted.forEach(row => container.appendChild(row));
}

function sortNotesContainer() {
	const container = document.getElementById("actual-notes-container");
	const rows = Array.from(container.querySelectorAll(".note-row"));
	const sorted = [...rows].sort((a, b) => {
		const typeA = a.querySelector("select[name='note_type']").value;
		const typeB = b.querySelector("select[name='note_type']").value;
		const indexA = NOTE_TYPE_ORDER.includes(typeA) ? NOTE_TYPE_ORDER.indexOf(typeA) : 99;
		const indexB = NOTE_TYPE_ORDER.includes(typeB) ? NOTE_TYPE_ORDER.indexOf(typeB) : 99;
		return indexA - indexB;
	});

	// bail out entirely if nothing needs to move — avoids
	// needless reparenting that can retrigger `revealed` hx-triggers
	const alreadySorted = sorted.every((row, i) => row === rows[i]);
	if (alreadySorted) return;

	sorted.forEach(row => container.appendChild(row));
}


function colorBOMAndActualParts() {
	const bomPartsContainer = document.getElementById("bom-list-form")
	const actualPartsContainer = document.getElementById("actual-parts-container")
	const bomPartsRows = Array.from(bomPartsContainer.querySelectorAll(".bom-part-row"))
	const actualPartsRows = Array.from(actualPartsContainer.querySelectorAll(".part-row"))

	partQuantityComparison = {}

	bomPartsRows.forEach((row) => {
		const partName = row.getAttribute('data-part-name')
		const theoreticalQuantity = parseInt(row.getAttribute('data-part-quantity'), 10)

		if (partName in partQuantityComparison) {

			partQuantityComparison[partName]["theoreticalQuantity"] +=  theoreticalQuantity

		}
		else {
			partQuantityComparison[partName] = {}
			partQuantityComparison[partName]["theoreticalQuantity"] = theoreticalQuantity
			partQuantityComparison[partName]["actualQuantity"] = 0
		}
	});

	actualPartsRows.forEach((row) => {
		const partName = row.querySelector(".part-row-part-name").value
		const actualQuantity = parseInt(row.querySelector(".part-row-part-quantity").value, 10)

		if (partName in partQuantityComparison) {

			partQuantityComparison[partName]["actualQuantity"] += actualQuantity

		}
		else {
			partQuantityComparison[partName] = {}
			partQuantityComparison[partName]["actualQuantity"] = actualQuantity
			partQuantityComparison[partName]["theoreticalQuantity"] = 0
		}
	});

	if (actualPartsRows && bomPartsRows && actualPartsRows.length > 0 && bomPartsRows.length > 0) {

		bomPartsRows.forEach((row) => {
			const partName = row.getAttribute('data-part-name')
			const quantityElem = row.querySelector(".bom-part-quantity")
			for (const [part, quantities] of Object.entries(partQuantityComparison)) {
				if (partName == part) {
					if (quantities["theoreticalQuantity"] != quantities["actualQuantity"]) {
						if (quantities["actualQuantity"] != 0) {

							quantityElem.classList.add("mismatched-part-row");
						}
						else {
							row.classList.add("mismatched-part-row");
						}
					}
					else {
						row.classList.remove("mismatched-part-row");
						quantityElem.classList.remove("mismatched-part-row");
					}
					break;
				}
			}
		});

		actualPartsRows.forEach((row) => {
			const partName = row.querySelector(".part-row-part-name").value
			const quantityElem = row.querySelector(".part-row-quantity-container")

			for (const [part, quantities] of Object.entries(partQuantityComparison)) {
				if (partName == part) {
					if (quantities["theoreticalQuantity"] != quantities["actualQuantity"]) {
						if (quantities["theoreticalQuantity"] != 0) {
							quantityElem.classList.add("mismatched-part-row");
						}
						else {
							row.classList.add("mismatched-part-row");
						}
					}
					else {
						row.classList.remove("mismatched-part-row");
						quantityElem.classList.remove("mismatched-part-row");
					}
					break;
				}
			}
		});
	}
	else {
		bomPartsRows.forEach((row) => {
			row.classList.remove("mismatched-part-row");
			row.querySelector(".bom-part-quantity").classList.remove("mismatched-part-row")
		})
		actualPartsRows.forEach((row) => {
			row.classList.remove("mismatched-part-row");
			row.querySelector(".part-row-quantity-container").classList.remove("mismatched-part-row")
		})
	}
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

	if (!lotSelect) return;

	if (partRow.dataset.hasExistingLot === "true")  {
		partRow.dataset.lastDefaultedType = selectedPartType.value;
		return;
	}

	if (selectedPartType.value === "CONNECTOR" || selectedPartType.value === "MISC") {
		lotSelect.value = "NA";
	}
	else {
		lotSelect.value = "Choose";
	}
}

document.addEventListener("DOMContentLoaded", () => {
	document.body.addEventListener("change", (e) => {
		const root = e.target
		const select = e.target.closest("select[name='part_type']");
		const buildList = e.target.closest(".actual-parts-container");
		const note_type = e.target.closest(".actual-notes-container");

		if (buildList) {
			colorBOMAndActualParts();
		}

		if (note_type) {
			sortNotesContainer();
		}

		if (!select) {
			if (root.getAttribute('name') === 'lot-select' || root.getAttribute('name') === 'custom-lot-input') {
			root.closest(".part-row").dataset.hasExistingLot = "true";
			}
			return
		}
		
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
		sortNotesContainer();
		colorBOMAndActualParts();
	});
});

function addTimerToConfirmPageIfYellowFlagsFound(yellowFlagsFound) {
	const confirmButton = document.getElementById('save-confirm-button');
	if (!yellowFlagsFound) return;

	confirmButton.disabled = true;

	totalTime = 5000;
	interval = 100;

	timeElapsed = 0;
	timeRemaining = totalTime;
	
	timerInterval = setInterval(() => {
		timeRemaining = timeRemaining - interval
		confirmButton.textContent = `Ready in ${timeRemaining / 1000.0}s`
	}, interval);
	setTimeout(() => {
		clearInterval(timerInterval)
		confirmButton.disabled = false;
		confirmButton.textContent = 'Confirm'
	}, totalTime);
};


document.addEventListener("htmx:afterSwap", function (event) {
    const target = event.detail.target;

        if (!target || target.id !== "generic-popup") {
        return;
    }
    const popup = document.getElementById("generic-popup");

    const yellowFlagsFound = popup.dataset.yellowFlagsFound === "true";

    addTimerToConfirmPageIfYellowFlagsFound(yellowFlagsFound);
});

function toggleSecretFileUploadContainer(fileUploadContainer, currentDisplayType) {
	if (currentDisplayType == "none") {
		fileUploadContainer.style.display = "grid"
	}
	else if (currentDisplayType == "grid") {
		fileUploadContainer.style.display = "none"
	}
}

document.addEventListener("DOMContentLoaded", () => {
	document.body.addEventListener("click", (event) => {

		if (event.ctrlKey) {
			const target = event.target;

			if (!target || target.id !== "vdi-logo") {
				return
			}

			fileUploadContainer = document.getElementById('secret-file-upload-container')
			
			currentDisplayType = window.getComputedStyle(fileUploadContainer).display;
			toggleSecretFileUploadContainer(fileUploadContainer, currentDisplayType);
		}
	});
});