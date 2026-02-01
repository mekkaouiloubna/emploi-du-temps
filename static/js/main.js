// Initialize Bootstrap tooltips and popovers
document.addEventListener("DOMContentLoaded", () => {
  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
  const bootstrap = window.bootstrap // Declare the bootstrap variable
  tooltipTriggerList.map((tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl))

  // Initialize popovers
  const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
  popoverTriggerList.map((popoverTriggerEl) => new bootstrap.Popover(popoverTriggerEl))

  // Auto-hide alerts after 5 seconds
  const alerts = document.querySelectorAll(".alert")
  alerts.forEach((alert) => {
    setTimeout(() => {
      const bsAlert = new bootstrap.Alert(alert)
      bsAlert.close()
    }, 5000)
  })
})

// Utility function for AJAX requests
async function makeRequest(url, method = "GET", data = null) {
  try {
    const options = {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    }

    if (data && method !== "GET") {
      options.body = JSON.stringify(data)
    }

    const response = await fetch(url, options)
    return await response.json()
  } catch (error) {
    console.error("Request failed:", error)
    return null
  }
}

// Mark notification as read
function markNotificationRead(notificationId) {
  makeRequest(`/teacher/notifications/${notificationId}/read`, "POST").then((data) => {
    if (data && data.status === "ok") {
      location.reload()
    }
  })
}

// Delete availability
function deleteAvailability(availabilityId) {
  if (confirm("Êtes-vous sûr de vouloir supprimer ce créneau de disponibilité ?")) {
    document.getElementById(`avail-form-${availabilityId}`).submit()
  }
}
