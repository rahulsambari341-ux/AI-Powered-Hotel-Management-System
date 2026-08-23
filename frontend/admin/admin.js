// Phase 9.5: see ../config.js - same pattern as the customer UI.
const API_BASE = window.HOTEL_API_BASE || "http://localhost:8000";

const loadStatus = document.getElementById("loadStatus");
const statGrid = document.getElementById("statGrid");
const refreshBtn = document.getElementById("refreshBtn");

// Global store for live search filtering
let allRecentBookings = [];
let availableRoomsList = [];

// Step 2: Filter panel elements
const filterPanel = document.getElementById("filterPanel");
const filterTitle = document.getElementById("filterTitle");
const filterHead = document.getElementById("filterHead");
const filterBody = document.getElementById("filterBody");
const closeFilterBtn = document.getElementById("closeFilterBtn");

function money(n) {
  return "\u20b9" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request to ${path} failed (${res.status})`);
  }

  return res.json();
}

function renderStats(stats) {
  document.getElementById("statOccupancy").textContent = `${stats.occupancy_percentage}%`;

  document.getElementById("statOccupancySub").textContent =
    `${stats.occupied_rooms} occupied / ${stats.total_rooms} total`;

  document.getElementById("statRevenue").textContent = money(stats.revenue);

  document.getElementById("statToday").textContent = stats.today_bookings;

  document.getElementById("statTotal").textContent = stats.total_bookings;

  document.getElementById("statBreakdown").textContent =
    `${stats.confirmed_bookings} confirmed \u00b7 ${stats.cancelled_bookings} cancelled`;

  document.getElementById("statCancelled").textContent =
    stats.cancelled_bookings;

  document.getElementById("statModified").textContent =
    stats.modified_bookings ?? 0;

  document.getElementById("statAvailable").textContent =
    stats.available_rooms;

  document.getElementById("statAvailableSub").textContent =
    `of ${stats.total_rooms} total rooms`;

  document.getElementById("statCustomers").textContent =
    stats.total_customers;
}

function renderBookings(bookings) {
  const body = document.getElementById("bookingsBody");

  if (bookings.length === 0) {
    body.innerHTML =
      `<tr><td colspan="8" class="empty-row">No matching bookings found</td></tr>`;
    return;
  }

  body.innerHTML = bookings.map(b => `
    <tr>
      <td class="mono">${b.booking_id}</td>
      <td>${b.customer_name ?? "—"}</td>
      <td>${b.room_type ?? "—"} (${b.room_number ?? "—"})</td>
      <td class="mono">${b.check_in}</td>
      <td class="mono">${b.check_out}</td>
      <td class="mono">${money(b.total_amount)}</td>
      <td>
        <span class="status-badge status-${b.booking_status}">
          ${b.booking_status}
        </span>
      </td>
      <td>
        <button onclick="adminCancel('${b.booking_id}')" style="background:#ef4444; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:12px; margin-right:4px;">Cancel</button>
        <button onclick="adminModify('${b.booking_id}', '${b.customer_name ?? ""}', '${b.check_in}', '${b.check_out}')" style="background:#3b82f6; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:12px;">Modify</button>
      </td>
    </tr>
  `).join("");
}

function renderCustomers(customers) {
  const body = document.getElementById("customersBody");

  if (customers.length === 0) {
    body.innerHTML =
      `<tr><td colspan="4" class="empty-row">No customers yet</td></tr>`;
    return;
  }

  body.innerHTML = customers.map(c => `
    <tr>
      <td>${c.name}</td>
      <td class="mono">${c.phone}</td>
      <td>${c.email ?? "—"}</td>
      <td class="mono">${c.booking_count}</td>
    </tr>
  `).join("");
}


/* =========================================================
   LIVE SEARCH FILTERING FOR RECENT BOOKINGS
   ========================================================= */

function filterRecentBookings() {
  const searchInput = document.getElementById("bookingSearchInput");
  if (!searchInput) return;
  
  const query = searchInput.value.toLowerCase().trim();

  const filtered = allRecentBookings.filter(b => {
    return (
      (b.booking_id && b.booking_id.toLowerCase().includes(query)) ||
      (b.customer_name && b.customer_name.toLowerCase().includes(query)) ||
      (b.room_number && b.room_number.toString().includes(query)) ||
      (b.room_type && b.room_type.toLowerCase().includes(query)) ||
      (b.check_in && b.check_in.includes(query)) ||
      (b.check_out && b.check_out.includes(query)) ||
      (b.booking_status && b.booking_status.toLowerCase().includes(query))
    );
  });

  renderBookings(filtered);
}


/* =========================================================
   STEP 2 & 3 - CLICKABLE STAT CARD DETAILS & SEPARATE LISTS
   ========================================================= */

const FILTER_CONFIG = {

  occupancy: {
    title: "Today's Occupied Rooms",
    endpoint: "/admin/rooms/occupied"
  },

  revenue: {
    title: "Revenue by Room",
    endpoint: "/admin/revenue/rooms"
  },

  today: {
    title: "Today's Bookings",
    endpoint: "/admin/bookings/today"
  },

  "all-bookings": {
    title: "All Bookings",
    endpoint: "/admin/bookings/all"
  },

  cancelled: {
    title: "Cancelled Bookings",
    endpoint: "/admin/bookings/cancelled"
  },

  modified: {
    title: "Modified Bookings",
    endpoint: "/admin/bookings/modified"
  },

  "available rooms": {
    title: "Available Rooms",
    endpoint: "/admin/rooms/available"
  },

  customers: {
    title: "Customers",
    endpoint: "/admin/customers"
  }
};


/*
  Small helper to safely display values.
*/
function displayValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  return value;
}


/*
  Convert API object keys into readable table headings.
*/
function formatHeading(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}


/*
  Render any list returned by the Step 2/3 admin endpoints.
*/
function renderFilterTable(data) {
  if (!Array.isArray(data) || data.length === 0) {
    filterHead.innerHTML = "";
    filterBody.innerHTML = `
      <tr>
        <td class="empty-row">No records found.</td>
      </tr>
    `;
    return;
  }

  const columns = Object.keys(data[0]);

  filterHead.innerHTML = `
    <tr>
      ${columns.map(column => `
        <th>${formatHeading(column)}</th>
      `).join("")}
    </tr>
  `;

  filterBody.innerHTML = data.map(row => `
    <tr>
      ${columns.map(column => {
        const value = row[column];

        if (
          column === "revenue" ||
          column === "total_amount" ||
          column === "room_revenue"
        ) {
          return `<td class="mono">${money(value)}</td>`;
        }

        if (column === "booking_status") {
          return `<td><span class="status-badge status-${value}">${value}</span></td>`;
        }

        return `<td>${displayValue(value)}</td>`;
      }).join("")}
    </tr>
  `).join("");
}


/*
  Load the data belonging to the clicked dashboard card.
*/
async function loadFilter(filterName) {

  const config = FILTER_CONFIG[filterName];

  if (!config) {
    return;
  }

  filterTitle.textContent = config.title;

  filterPanel.hidden = false;

  filterHead.innerHTML = "";

  filterBody.innerHTML = `
    <tr>
      <td class="empty-row">Loading…</td>
    </tr>
  `;

  try {

    const data = await fetchJSON(config.endpoint);

    renderFilterTable(data);

    filterPanel.scrollIntoView({
      behavior: "smooth",
      block: "start"
    });

  } catch (err) {

    filterHead.innerHTML = "";

    filterBody.innerHTML = `
      <tr>
        <td class="empty-row">
          Could not load data: ${err.message}
        </td>
      </tr>
    `;
  }
}


/*
  Attach click events to all dashboard cards.
*/
function setupClickableCards() {

  const cards = document.querySelectorAll(".clickable-card");

  cards.forEach(card => {

    card.addEventListener("click", () => {

      const filterName = card.dataset.filter;

      loadFilter(filterName);

    });

  });
}


/*
  Close the filter/details panel.
*/
if (closeFilterBtn) {

  closeFilterBtn.addEventListener("click", () => {

    filterPanel.hidden = true;

  });

}


/* =========================================================
   DASHBOARD LOADING
   ========================================================= */

async function loadDashboard() {

  loadStatus.textContent = "Loading live data…";

  statGrid.hidden = true;

  refreshBtn.disabled = true;

  try {

    const [stats, bookings, customers] = await Promise.all([

      fetchJSON("/admin/stats"),

      fetchJSON("/admin/bookings/recent?limit=50"),

      fetchJSON("/admin/customers"),

    ]);

    renderStats(stats);

    // Save bookings globally and render table
    allRecentBookings = bookings;
    renderBookings(allRecentBookings);

    renderCustomers(customers);

    loadStatus.textContent = "";

    statGrid.hidden = false;

  } catch (err) {

    loadStatus.textContent =
      `Could not load dashboard data: ${err.message}`;

  } finally {

    refreshBtn.disabled = false;

  }

}


/* =========================================================
   EVENT LISTENERS & ACTIONS
   ========================================================= */

async function adminCancel(bookingId) {
  if (!confirm(`Are you sure you want to cancel booking ${bookingId}?`)) return;
  try {
    const res = await fetch(`${API_BASE}/admin/bookings/${bookingId}/cancel`, { method: "POST" });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to cancel booking");
    }
    loadDashboard(); // Refresh UI instantly
  } catch (err) {
    alert("Error: " + err.message);
  }
}

function adminModify(bookingId, customerName, checkIn, checkOut) {
  const modal = document.getElementById("editModal");
  if (!modal) {
    // Prompts asking Name, Phone, Email, Adults, Children, Room ID, Check-in, Check-out sequentially
    const newName = prompt(`Modify Customer Name for ${bookingId}:`, customerName || "");
    if (newName === null) return;
    const newPhone = prompt(`Modify Customer Phone for ${bookingId}:`, "");
    if (newPhone === null) return;
    const newEmail = prompt(`Modify Customer Email for ${bookingId}:`, "");
    if (newEmail === null) return;
    const newAdults = prompt(`Modify Adults count for ${bookingId}:`, "1");
    if (newAdults === null) return;
    const newChildren = prompt(`Modify Children count for ${bookingId}:`, "0");
    if (newChildren === null) return;
    const newRoomId = prompt(`Modify Room ID for ${bookingId}:`, "");
    if (newRoomId === null) return;
    const newCheckIn = prompt(`Modify Check-In date for ${bookingId} (YYYY-MM-DD):`, checkIn || "");
    if (newCheckIn === null) return;
    const newCheckOut = prompt(`Modify Check-Out date for ${bookingId} (YYYY-MM-DD):`, checkOut || "");
    if (newCheckOut === null) return;

    const payload = {};
    if (newName.trim() !== "") payload.customer_name = newName.trim();
    if (newPhone.trim() !== "") payload.customer_phone = newPhone.trim();
    if (newEmail.trim() !== "") payload.customer_email = newEmail.trim();
    if (newAdults.trim() !== "" && !isNaN(newAdults)) payload.adults = parseInt(newAdults.trim(), 10);
    if (newChildren.trim() !== "" && !isNaN(newChildren)) payload.children = parseInt(newChildren.trim(), 10);
    if (newRoomId.trim() !== "" && !isNaN(newRoomId)) payload.room_id = parseInt(newRoomId.trim(), 10);
    if (newCheckIn.trim() !== "") payload.check_in = newCheckIn.trim();
    if (newCheckOut.trim() !== "") payload.check_out = newCheckOut.trim();

    fetch(`${API_BASE}/admin/bookings/${bookingId}/update`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(async res => {
      if (res.ok) {
        loadDashboard();
        alert(`Booking ${bookingId} updated successfully!`);
      } else {
        const errData = await res.json().catch(() => ({}));
        alert("Failed to update booking: " + (errData.detail || "Server error"));
      }
    }).catch(err => alert("Error: " + err.message));
    return;
  }

  const idEl = document.getElementById("editBookingId");
  const nameEl = document.getElementById("editCustomerName");
  const checkInEl = document.getElementById("editCheckIn");
  const checkOutEl = document.getElementById("editCheckOut");

  if (idEl) idEl.value = bookingId;
  if (nameEl) nameEl.value = customerName;
  if (checkInEl) checkInEl.value = checkIn || "";
  if (checkOutEl) checkOutEl.value = checkOut || "";
  modal.style.display = "flex";
}

function closeEditModal() {
  const modal = document.getElementById("editModal");
  if (modal) modal.style.display = "none";
}

async function submitEditBooking() {
  const bookingId = document.getElementById("editBookingId")?.value;
  const customer_name = document.getElementById("editCustomerName")?.value;
  const customer_phone = document.getElementById("editCustomerPhone")?.value;
  const customer_email = document.getElementById("editCustomerEmail")?.value;
  const room_id_val = document.getElementById("editRoomId")?.value;
  const room_id = room_id_val ? parseInt(room_id_val, 10) : null;
  const check_in = document.getElementById("editCheckIn")?.value;
  const check_out = document.getElementById("editCheckOut")?.value;

  if (!bookingId) {
    alert("Booking ID is missing.");
    return;
  }

  try {
    const payload = {};
    if (customer_name) payload.customer_name = customer_name;
    if (customer_phone) payload.customer_phone = customer_phone;
    if (customer_email) payload.customer_email = customer_email;
    if (!isNaN(room_id) && room_id !== null) payload.room_id = room_id;
    if (check_in) payload.check_in = check_in;
    if (check_out) payload.check_out = check_out;

    const res = await fetch(`${API_BASE}/admin/bookings/${bookingId}/update`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to update booking");
    }

    closeEditModal();
    loadDashboard(); // Refresh UI instantly with updated details
    alert(`Booking ${bookingId} updated successfully!`);
  } catch (err) {
    alert("Error: " + err.message);
  }
}

/* =========================================================
   NEW BOOKING MODAL & SUBMISSION FIXES
   ========================================================= */

async function openNewBookingModal() {
  const modal = document.getElementById("newBookingModal");
  if (modal) modal.style.display = "flex";
  
  // Reset form fields
  const todayStr = new Date().toISOString().split("T")[0];
  const nameInput = document.getElementById("newCustomerName");
  const phoneInput = document.getElementById("newCustomerPhone");
  const emailInput = document.getElementById("newCustomerEmail");
  const checkInInput = document.getElementById("newCheckIn");
  const checkOutInput = document.getElementById("newCheckOut");
  const totalInput = document.getElementById("newTotalAmount");

  if (nameInput) nameInput.value = "";
  if (phoneInput) phoneInput.value = "";
  if (emailInput) emailInput.value = "";
  if (checkInInput) {
    checkInInput.value = todayStr;
    checkInInput.min = todayStr;
  }
  if (checkOutInput) {
    checkOutInput.value = "";
    checkOutInput.min = todayStr;
  }
  if (totalInput) totalInput.value = "0";

  const select = document.getElementById("newRoomSelect");
  if (!select) return;
  select.innerHTML = '<option value="">Loading available rooms...</option>';

  try {
    const rooms = await fetchJSON("/admin/rooms/available");
    availableRoomsList = rooms;

    if (!rooms || rooms.length === 0) {
      select.innerHTML = '<option value="">No available rooms found</option>';
      return;
    }

    select.innerHTML = '<option value="">-- Select an Available Room --</option>' + rooms.map(r => {
      let price = 2500;
      const type = (r.room_type || "").toLowerCase();
      if (type.includes("standard")) price = 1800;
      else if (type.includes("deluxe")) price = 2500;
      else if (type.includes("premium")) price = 4000;
      else if (type.includes("suite")) price = 7000;

      // Ensure room id is correctly mapped
      const roomId = r.id || r.room_id;
      const roomNum = r.room_number || "";
      const roomType = r.room_type || "Room";

      return `
        <option value="${roomId}" data-price="${price}">
          Room ${roomNum} (${roomType}) - ₹${price}/night
        </option>
      `;
    }).join("");
  } catch (err) {
    select.innerHTML = '<option value="">Failed to load rooms</option>';
  }
}

function closeNewBookingModal() {
  const modal = document.getElementById("newBookingModal");
  if (modal) modal.style.display = "none";
}

function calculateBookingAmount() {
  const select = document.getElementById("newRoomSelect");
  if (!select) return;

  const selectedOption = select.options[select.selectedIndex];
  const pricePerNight = parseFloat(selectedOption?.dataset?.price || 0);

  const checkInInput = document.getElementById("newCheckIn");
  const checkOutInput = document.getElementById("newCheckOut");
  const totalInput = document.getElementById("newTotalAmount");

  if (!checkInInput || !checkOutInput || !totalInput) return;

  const checkInVal = checkInInput.value;
  const checkOutVal = checkOutInput.value;

  if (!checkInVal || !checkOutVal || !selectedOption || select.value === "") {
    totalInput.value = "0";
    return;
  }

  const d1 = new Date(checkInVal);
  const d2 = new Date(checkOutVal);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (isNaN(d1.getTime()) || isNaN(d2.getTime()) || d1 < today || d2 <= d1) {
    totalInput.value = "0";
    return;
  }

  const diffTime = d2 - d1;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  totalInput.value = diffDays * pricePerNight;
}

async function submitNewBooking() {
  const nameEl = document.getElementById("newCustomerName");
  const phoneEl = document.getElementById("newCustomerPhone");
  const emailEl = document.getElementById("newCustomerEmail");
  const roomSelect = document.getElementById("newRoomSelect");
  const checkInEl = document.getElementById("newCheckIn");
  const checkOutEl = document.getElementById("newCheckOut");
  const totalEl = document.getElementById("newTotalAmount");

  const customer_name = nameEl ? nameEl.value.trim() : "";
  const customer_phone = phoneEl ? phoneEl.value.trim() : "";
  const customer_email = emailEl ? emailEl.value.trim() : "";
  
  // Robust room ID extraction
  const room_id = roomSelect && roomSelect.value ? parseInt(roomSelect.value, 10) : null;
  
  const check_in = checkInEl ? checkInEl.value : "";
  const check_out = checkOutEl ? checkOutEl.value : "";
  const total_amount = totalEl ? parseFloat(totalEl.value) : 0;

  // Validations
  if (!customer_name) {
    alert("Please enter the guest's name.");
    return;
  }

  const phoneRegex = /^[0-9]{10}$/;
  if (!customer_phone || !phoneRegex.test(customer_phone)) {
    alert("Please enter a valid 10-digit phone number.");
    return;
  }

  if (!room_id || isNaN(room_id)) {
    alert("Please select a valid available room from the dropdown.");
    return;
  }
  if (!check_in) {
    alert("Please select a check-in date.");
    return;
  }
  if (!check_out) {
    alert("Please select a check-out date.");
    return;
  }

  const d1 = new Date(check_in);
  const d2 = new Date(check_out);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  if (d1 < today) {
    alert("Check-in date cannot be in the past.");
    return;
  }
  if (d2 <= d1) {
    alert("Check-out date must be strictly after the check-in date.");
    return;
  }
  if (isNaN(total_amount) || total_amount <= 0) {
    alert("Invalid total amount. Please verify your selected dates and room.");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/admin/bookings/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_name,
        customer_phone,
        customer_email: customer_email || null,
        room_id,
        check_in,
        check_out,
        total_amount,
        adults: Number(document.getElementById("newAdults").value) || 1,
        children: Number(document.getElementById("newChildren").value) || 0
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to create booking");
    }

    const data = await res.json();
    closeNewBookingModal();
    loadDashboard(); // Refresh UI instantly
    alert(`Booking created successfully! ID: ${data.booking_id}`);
  } catch (err) {
    alert("Error: " + err.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (refreshBtn) refreshBtn.addEventListener("click", loadDashboard);
  setupClickableCards();
  loadDashboard();
});