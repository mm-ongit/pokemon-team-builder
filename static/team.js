console.log("team.js loaded ✅")

const form = document.getElementById("search-form");
const input = document.getElementById("pokemon-input");
const statusEl = document.getElementById("search-status");
const resultEl = document.getElementById("search-result");
const teamGrid = document.getElementById("team-grid");
const teamNameInput = document.getElementById("team-name");
const saveBtn = document.getElementById("save-team-btn");
const saveStatusEl = document.getElementById("save-status");

function setSaveStatus(msg) {
    saveStatusEl.textContent = msg || "";
}

// If any of these shows as null in the console HTML ids don't match what JS expects
console.log({ form, input, statusEl, resultEl, teamGrid });

let currentPokemon = null; // Create a Pokemon object
let team = []; // Array of Pokemon objects

function setStatus(msg) {
    statusEl.textContent = msg || "";
}

function renderResult(p) {
    if (!p) {
        resultEl.innerHTML = "";
        return;
    }

    const typesText = p.types.map(t => t[0].toUpperCase() + t.slice(1)).join(", ");

    resultEl.innerHTML = `
        <div class="pokemon-card">
            <img src="${p.sprite || ""}" alt="${p.name}">
            <div>
                <p class="pokemon-name">${p.name}</p>
                <p class="pokemon-types">Types: ${typesText}</p>
                <button id="add-to-team-btn" type="button">Add to team</button>
            </div>
        </div>
        `;

    document.getElementById("add-to-team-btn").addEventListener("click", () => {
        addToTeam(p);
    });
}

function renderTeam() {
    if (team.length === 0) {
        teamGrid.innerHTML = `<p class="muted">No Pokémon added to team. Search and add up to 6.</p>`;
        return;
    }

    // Concise map over verbose map
    teamGrid.innerHTML = team.map((p, idx) => `
        <div class="team-slot">
            <img src="${p.sprite || ""}" alt="${p.name}">
            <div>
                <div class="pokemon-name">${p.name}</div>
                <div class="muted">${p.types.join(", ")}</div>
            </div>
            <button type="button" data-remove="${idx}">Remove</button>
        </div>
    `).join("");
}

function addToTeam(p) {
    if (team.length >= 6) {
        setStatus("Team is full (max 6). Remove one first.");
        return;
    }

    const already = team.some(x => x.id === p.id);
    if (already) {
        setStatus("That Pokémon is already on your team.");
        return;
    }

    team.push(p);
    renderTeam();
    setStatus(`Added ${p.name} to your team.`);
}

async function fetchPokemon(name) {
    setStatus("Searching...");
    renderResult(null);
    currentPokemon = null;

    try {
        const resp = await fetch(`/api/pokemon/${encodeURIComponent(name)}`);
        const data = await resp.json();

        if (!resp.ok) {
            setStatus(data.error || "Search failed.");
            return;
        }

        // Normalize types for display
        data.types = data.types.map(t => t[0].toUpperCase() + t.slice(1));

        currentPokemon = data;
        setStatus("");
        renderResult(currentPokemon);
    } catch (err) {
        setStatus("Network error. Try again.")
    }
}

async function saveTeam() {
    const name = teamNameInput.value.trim();

    if (!name) {
        setSaveStatus("Please enter a team name.");
        return;
    }
    if (team.length === 0) {
        setSaveStatus("Add at least 1 Pokémon before saving.");
        return;
    }

    setSaveStatus("Saving...");

    try {
        const resp = await fetch("/api/teams", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, pokemon: team }),
        });

        const data = await resp.json();

        if (!resp.ok) {
            setSaveStatus(data.error || "Save failed");
            return;
        }

        setSaveStatus("Saved! Check My Teams");
    } catch (err) {
        setSaveStatus("Network error while saving")
    }
}

form.addEventListener("submit", (e) => {
    e.preventDefault();
    const name = input.value.trim();
    if (!name) return;
    fetchPokemon(name);
});

// Event Delegation Listener
teamGrid.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-remove]");
    if (!btn) return;

    const idx = Number(btn.getAttribute("data-remove"));
    if (Number.isNaN(idx)) return;

    team.splice(idx, 1);
    renderTeam();
    setStatus("")
})

saveBtn.addEventListener("click", saveTeam);

renderTeam();