const PART_TYPE_ORDER = ["MMIC", "DIODE", "CIRCUIT", "PCB", "FILTER", "N/A", "MISC", "CONNECTOR"];
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
