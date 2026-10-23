"""Exercise the local Worker with synthetic data (never the remote database)."""
import uuid
import httpx


def check():
    with httpx.Client(base_url='http://127.0.0.1:8787', timeout=60, follow_redirects=True) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response

        assert request('GET', '/api/health').json()['storage'] == 'cloudflare-d1'
        for path in ['/', '/approval', '/dashboard', '/static/app.js', '/static/experience.js', '/static/style.css']:
            assert request('GET', path).content
        catalog = request('GET', '/api/catalog').json()
        assert len(catalog) == 8
        details = {'full_name': 'Worker Test', 'email': f'worker-{uuid.uuid4().hex[:10]}@example.com',
                   'department': 'Engineering', 'job_title': 'Software engineer',
                   'manager': 'Jordan Example', 'start_date': '2026-11-01'}

        def create(email=None):
            return request('POST', '/api/hires', json={**details, 'email': email or details['email'],
                'assignments': [{'tool': t['id']} for t in catalog]}).json()

        def approve(hire):
            return request('POST', f'/api/hires/{hire["id"]}/decision', json={
                'revision': hire['revision'], 'decision': 'approve', 'confirmed': True}).json()

        hire = create()
        assert hire['status'] == 'pending_approval'
        result = approve(hire)
        assert all(r['status'] == 'created' for r in result['results'])
        assert all(r['actual_role'] == r['requested_role'] for r in result['results'])
        assert next(r for r in result['results'] if r['tool'] == 'github')['actual_role'] == 'viewer'
        assert approve(hire) == result
        reused = approve(create('existing@example.com'))
        assert sum(r['status'] == 'already_existed' for r in reused['results']) >= 3
        info = request('GET', '/api/mock/salesforce/inspect').json()
        try:
            request('PUT', '/api/mock/salesforce/settings', json={
                'total': info['seats']['used'], 'default_role': info['default_role']})
            partial = approve(create(f'seat-{uuid.uuid4().hex[:10]}@example.com'))
            rows = {r['tool']: r for r in partial['results']}
            assert rows['salesforce']['status'] == 'partial'
            assert sum(r['status'] == 'created' for r in rows.values()) == 7
        finally:
            request('PUT', '/api/mock/salesforce/settings', json={
                'total': info['seats']['total'], 'default_role': info['default_role']})
        recommended = request('POST', '/api/hires/recommend', json={**details,
            'responsibilities': 'Write backend code and review pull requests.'}).json()
        assert recommended['status'] == 'pending_approval'
        assert recommended['agent_mode'] == 'rules'  # Run this check without AI keys.
        print('PASS: static pages/assets, health, eight-app approval, exact roles, repeat approval, existing accounts, seat limits, and labeled recommendation fallback in the Workers runtime.')


if __name__ == '__main__':
    check()
