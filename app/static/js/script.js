async function sendQuery() {

    const affiliate_id = document.getElementById("affiliate_id").value;
    const query = document.getElementById("query").value;

    document.getElementById("estado").innerText = "Consultando...";
    document.getElementById("explicacion").innerText = "";
    document.getElementById("fuentes").innerHTML = "";

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minutos

    try {
        const response = await fetch("/api/consulta", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ afiliado_id: affiliate_id, consulta: query }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        const data = await response.json();

        document.getElementById("estado").innerText = data.estado;
        document.getElementById("explicacion").innerText = data.explicacion;

        const fuentesList = document.getElementById("fuentes");
        fuentesList.innerHTML = "";
        (data.fuentes || []).forEach(f => {
            const li = document.createElement("li");
            li.textContent = f;
            fuentesList.appendChild(li);
        });

    } catch (err) {
        clearTimeout(timeoutId);
        document.getElementById("estado").innerText = "Error: " + (err.name === "AbortError" ? "Timeout — el modelo tardó demasiado" : err.message);
    }
}