// static/js/usuarios.js
document.addEventListener('DOMContentLoaded', function() {
    const formUsuario = document.getElementById('formUsuario');
    const formUsuarioEdit = document.getElementById('formUsuarioEdit');
    const usernameInput = document.getElementById('username');

    // Validación Contraseñas Creación
    if (formUsuario) {
        formUsuario.addEventListener('submit', function(e) {
            const pass1 = document.getElementById('password')?.value;
            const pass2 = document.getElementById('password_confirm')?.value;

            if (pass1 !== pass2) {
                e.preventDefault();
                alert('Las contraseñas no coinciden. Por favor, verifica.');
            }
        });
    }

    // Validación Contraseñas Edición
    if (formUsuarioEdit) {
        formUsuarioEdit.addEventListener('submit', function(e) {
            const pass1 = document.getElementById('password')?.value;
            const pass2 = document.getElementById('password_confirm')?.value;

            // En edición, password puede ser opcional
            if (pass1 !== pass2) {
                e.preventDefault();
                alert('Las nuevas contraseñas no coinciden. Por favor asegúrate de que sean exactas o déjalas en blanco para mantener la anterior.');
            }
        });
    }

    // Prevenir espacios en blanco en tiempo real para el username
    if (usernameInput) {
        usernameInput.addEventListener('input', function(e) {
            this.value = this.value.replace(/\s+/g, '');
        });
    }
});
