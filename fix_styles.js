const fs = require('fs');

const files = ['/dashboard/app/static/js/app.js', '/dashboard/app/static/js/cards.js'];

for (const file of files) {
    let content = fs.readFileSync(file, 'utf8');

    content = content.replace(/color:\s*var\(--gray\)/g, 'color: var(--text-muted)');
    content = content.replace(/color:\s*#666/g, 'color: var(--text-muted)');
    content = content.replace(/color:\s*#ccc/g, 'color: var(--border-color)');
    content = content.replace(/background:\s*#f8d7da/g, 'background: var(--danger-bg)');
    content = content.replace(/color:\s*#721c24/g, 'color: var(--danger-text)');
    content = content.replace(/border:\s*1px\s+solid\s*#f5c6cb/g, 'border: 1px solid var(--danger-border)');
    content = content.replace(/background:\s*#f8f9fa/g, 'background: var(--code-bg)');
    content = content.replace(/background:\s*#fcfcfc/g, 'background: var(--card-bg-alt)');
    content = content.replace(/border:\s*1px\s+solid\s*#eee/g, 'border: 1px solid var(--border-color)');

    fs.writeFileSync(file, content);
}
console.log('Fixed inline styles');
