const fs = require('fs');

const files = ['/dashboard/app/static/js/app.js', '/dashboard/app/static/js/cards.js'];

for (const file of files) {
    let content = fs.readFileSync(file, 'utf8');

    // Text colors
    content = content.replace(/color:\s*var\(--gray\)/g, 'color: var(--text-muted)');
    content = content.replace(/color:\s*#666/g, 'color: var(--text-muted)');
    content = content.replace(/color:\s*#ccc/g, 'color: var(--text-muted)');
    content = content.replace(/color:\s*#aaa/g, 'color: var(--text-muted)');
    content = content.replace(/fill="#666"/g, 'fill="var(--text-muted)"');
    content = content.replace(/fill="#aaa"/g, 'fill="var(--text-muted)"');

    // Backgrounds and Borders
    content = content.replace(/background:\s*#f8f9fa/g, 'background: var(--code-bg)');
    content = content.replace(/background:\s*#fcfcfc/g, 'background: var(--card-bg-alt)');
    content = content.replace(/border:\s*1px\s+solid\s*#eee/g, 'border: 1px solid var(--border-color)');
    content = content.replace(/border-bottom:\s*2px\s+solid\s*var\(--light\)/g, 'border-bottom: 2px solid var(--border-color)');

    // SVG strokes
    content = content.replace(/stroke="#ccc"/g, 'stroke="var(--border-color)"');
    content = content.replace(/stroke="#eee"/g, 'stroke="var(--border-color)"');

    // Code blocks
    content = content.replace(/color:\s*#721c24/g, 'color: var(--danger-text)');

    fs.writeFileSync(file, content);
}
console.log('Fixed inline styles v2');
