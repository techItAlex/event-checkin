// Small client-side validation (the server validates again).
document.getElementById('regform').addEventListener('submit', e => {
  const f = e.target;
  const digits = f.contact_number.value.replace(/[\s-]/g, '');
  if (!/^\+?\d{10,13}$/.test(digits)) {
    e.preventDefault();
    alert('Contact number must be 10 to 13 digits, e.g. 09171234567 or +639171234567.');
    return;
  }
  if (!f.checkValidity()) {
    e.preventDefault();
    f.reportValidity();
  }
});
