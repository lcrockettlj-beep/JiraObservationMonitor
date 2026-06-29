async function loadNamedAccess() {
    try {
        const res = await fetch('/static/data/user_footprint.json');
        const data = await res.json();

        if (data.source_status !== 'generated') {
            document.getElementById('namedAccessContainer').innerHTML =
                '<div class="truth-unavailable">Named access not available</div>';
            return;
        }

        let html = 
            <table class="na-table">
                <thead>
                    <tr>
                        <th>User</th>
                        <th>Sites</th>
                        <th>Site Count</th>
                        <th>Assignments</th>
                        <th>Category</th>
                    </tr>
                </thead>
                <tbody>
        ;

        data.users.forEach(u => {
            html += 
                <tr class="na-row na-">
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                    <td></td>
                </tr>
            ;
        });

        html += '</tbody></table>';

        document.getElementById('namedAccessContainer').innerHTML = html;

    } catch (e) {
        document.getElementById('namedAccessContainer').innerHTML =
            '<div class="truth-unavailable">Failed to load named access</div>';
    }
}

document.addEventListener('DOMContentLoaded', loadNamedAccess);
