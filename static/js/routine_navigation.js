/* Keep routine navigation tied to the source page, including its scroll position. */
(() => {
    const scrollKey = url => `cmfit:routine-return:${url}`;
    const currentPage = () => location.pathname + location.search + location.hash;

    document.querySelectorAll('[data-routine-link]').forEach(link => {
        link.addEventListener('click', () => {
            const source = currentPage();
            const routine = new URL(link.href, location.origin);
            routine.searchParams.set('return_to', source);
            link.href = routine.href;
            try {
                sessionStorage.setItem(scrollKey(source), String(window.scrollY));
            } catch (_) {
                // Links remain usable if browser storage is disabled.
            }
        });
    });

    const back = document.querySelector('[data-routine-back]');
    if (back) {
        const source = new URLSearchParams(location.search).get('return_to');
        if (source) {
            try {
                const destination = new URL(source, location.origin);
                const workouts = new URL(back.dataset.workoutsUrl, location.origin);
                const plan = new URL(back.dataset.planUrl, location.origin);
                if (destination.origin === location.origin &&
                    [workouts.pathname, plan.pathname].includes(destination.pathname)) {
                    back.href = destination.pathname + destination.search + destination.hash;
                    back.querySelector('span').textContent = destination.pathname === plan.pathname
                        ? (destination.searchParams.get('tab') === 'weekly' ? 'Back to Weekly plans' : 'Back to Annual plan')
                        : 'Back to Workouts';
                }
            } catch (_) {
                // Invalid or external destinations fall back to Workouts.
            }
        }
    } else if (document.querySelector('[data-routine-link]')) {
        window.addEventListener('pageshow', () => {
            try {
                const key = scrollKey(currentPage());
                const saved = sessionStorage.getItem(key);
                if (saved === null) return;
                sessionStorage.removeItem(key);
                const position = Number(saved);
                if (Number.isFinite(position) && position >= 0) {
                    requestAnimationFrame(() => window.scrollTo(0, position));
                }
            } catch (_) {
                // Native browser scroll restoration remains available.
            }
        });
    }
})();
