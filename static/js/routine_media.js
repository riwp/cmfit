/* Independent exercise galleries on the routine page. */
(() => {
    document.querySelectorAll('.routine-media-toggle').forEach(button => {
        const gallery = document.getElementById(button.getAttribute('aria-controls'));
        button.addEventListener('click', () => {
            gallery.hidden = !gallery.hidden;
            button.setAttribute('aria-expanded', String(!gallery.hidden));
            button.setAttribute('aria-label', button.getAttribute('aria-label')
                .replace(/^(Show|Hide)/, gallery.hidden ? 'Show' : 'Hide'));
        });
    });

    const lightbox = document.getElementById('routine-image-lightbox');
    if (!lightbox) return;
    const image = lightbox.querySelector('img');
    const closeButton = lightbox.querySelector('button');
    let opener = null;
    function close() {
        if (lightbox.hidden) return;
        lightbox.hidden = true;
        document.body.classList.remove('routine-image-open');
        opener?.focus();
    }
    document.querySelectorAll('.routine-image-preview').forEach(button => {
        button.addEventListener('click', () => {
            opener = button;
            image.src = button.dataset.imageSrc;
            image.alt = button.dataset.imageAlt;
            document.body.classList.add('routine-image-open');
            lightbox.hidden = false;
            closeButton.focus();
        });
    });
    closeButton.addEventListener('click', close);
    lightbox.addEventListener('click', event => { if (event.target === lightbox) close(); });
    lightbox.addEventListener('keydown', event => {
        if (event.key === 'Escape') close();
        if (event.key === 'Tab') { event.preventDefault(); closeButton.focus(); }
    });
})();
