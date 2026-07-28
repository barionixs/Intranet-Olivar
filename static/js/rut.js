function formatearRut(valor) {
  const limpio = valor.replace(/[^0-9kK]/g, "").toUpperCase();
  if (limpio.length < 2) {
    return limpio;
  }
  const dv = limpio.slice(-1);
  const cuerpo = limpio.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${cuerpo}-${dv}`;
}

document.querySelectorAll(".js-rut-input").forEach((campo) => {
  campo.addEventListener("blur", () => {
    campo.value = formatearRut(campo.value);
  });
});
