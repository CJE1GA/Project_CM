const columns = [
  { name: 'Full Training', slug: 'training', color: 'training' },
  { name: 'Wellness', slug: 'wellness', color: 'wellness' },
  { name: 'Running Club', slug: 'running', color: 'running' }
];

const startDate = new Date(2026, 8, 14);
const endDate = new Date(2026, 9, 13);
const labels = {
  A: 'Preparación Hyrox',
  B: 'Cómo recupero mi cuerpo',
  C: 'Runners club',
  D: 'Superación personal',
  E: 'Humor'
};
const typeNames = { reel: 'Reel', design: 'Diseño' };
const totalRules = { reel: 10, design: 4 };
const uploadPattern = ['Running Club', 'Wellness', 'Full Training'];
const categoryAPattern = ['Full Training', 'Running Club', 'Full Training', 'Wellness'];
const blockedUploadDays = [1, 2];
const tableRules = {
  reel: {
    'Full Training': { A: 2, B: 0, C: 0, D: 1, E: 1 },
    Wellness: { A: 1, B: 2, C: 0, D: 0, E: 0 },
    'Running Club': { A: 1, B: 0, C: 1, D: 1, E: 0 }
  },
  design: {
    'Full Training': { A: 0, B: 0, C: 0, D: 1, E: 0 },
    Wellness: { A: 0, B: 1, C: 0, D: 1, E: 0 },
    'Running Club': { A: 0, B: 0, C: 1, D: 0, E: 0 }
  }
};

const schedule = [
  ['2026-09-16', 2, 'C', 'reel'],
  ['2026-09-17', 1, 'B', 'design'],
  ['2026-09-18', 0, 'A', 'reel'],
  ['2026-09-23', 2, 'A', 'reel'],
  ['2026-09-24', 1, 'B', 'reel'],
  ['2026-09-25', 0, 'D', 'design'],
  ['2026-09-30', 2, 'D', 'reel'],
  ['2026-10-01', 1, 'B', 'reel'],
  ['2026-10-02', 0, 'A', 'reel'],
  ['2026-10-07', 2, 'C', 'design'],
  ['2026-10-08', 1, 'A', 'reel'],
  ['2026-10-09', 0, 'D', 'reel'],
  ['2026-10-10', 1, 'D', 'design'],
  ['2026-10-11', 0, 'E', 'reel']
];

function weekKey(date) {
  const weekStart = new Date(date);
  const dayOffset = (weekStart.getDay() + 6) % 7;
  weekStart.setDate(weekStart.getDate() - dayOffset);
  return weekStart.toISOString().slice(0, 10);
}

function emptyCategoryCounts() {
  return { A: 0, B: 0, C: 0, D: 0, E: 0 };
}

function getCalendarEvents() {
  return schedule.map(([date, columnIndex, letter, type]) => ({
    date: new Date(`${date}T12:00:00`),
    column: columns[columnIndex],
    letter,
    title: labels[letter],
    type
  }));
}

const events = getCalendarEvents();

function validateSchedule() {
  const totalCounts = Object.fromEntries(Object.keys(totalRules).map(type => [type, 0]));
  const tableCounts = {
    reel: Object.fromEntries(columns.map(column => [column.name, emptyCategoryCounts()])),
    design: Object.fromEntries(columns.map(column => [column.name, emptyCategoryCounts()]))
  };
  const reelsAByWeek = {};
  const categoryAEvents = [];
  let consecutiveReels = 0;

  const sortedEvents = events.slice().sort((first, second) => first.date - second.date);

  sortedEvents.forEach(event => {
    if (!totalCounts[event.type] && totalCounts[event.type] !== 0) {
      throw new Error(`El formato ${event.type} no debe mostrarse en el plan visible.`);
    }

    if (blockedUploadDays.includes(event.date.getDay())) {
      throw new Error('No se deben programar publicaciones los lunes ni los martes.');
    }

    totalCounts[event.type] += 1;
    consecutiveReels = event.type === 'reel' ? consecutiveReels + 1 : 0;

    if (consecutiveReels > 3) {
      throw new Error('Hay demasiados reels consecutivos en el calendario.');
    }

    if (event.letter === 'A' && event.type !== 'reel') {
      throw new Error('La categoria A solo puede usarse como reel.');
    }

    if (event.letter === 'A') {
      categoryAEvents.push(event);
      const key = weekKey(event.date);
      reelsAByWeek[key] = (reelsAByWeek[key] || 0) + 1;
      if (reelsAByWeek[key] > 1) {
        throw new Error('Hay mas de 1 reel de categoria A en la misma semana.');
      }
    }

    if (tableCounts[event.type]) {
      tableCounts[event.type][event.column.name][event.letter] += 1;
    }
  });

  const remainingByBrand = sortedEvents.reduce((counts, event) => {
    counts[event.column.name] = (counts[event.column.name] || 0) + 1;
    return counts;
  }, {});
  let patternIndex = 0;

  sortedEvents.forEach(event => {
    while (remainingByBrand[uploadPattern[patternIndex % uploadPattern.length]] === 0) {
      patternIndex += 1;
    }

    const expectedBrand = uploadPattern[patternIndex % uploadPattern.length];
    if (event.column.name !== expectedBrand) {
      throw new Error(`El patron de subida debe seguir ${uploadPattern.join(', ')}.`);
    }

    remainingByBrand[event.column.name] -= 1;
    patternIndex += 1;
  });

  categoryAEvents.forEach((event, index) => {
    if (event.column.name !== categoryAPattern[index]) {
      throw new Error(`El reel A de la semana ${index + 1} debe ser de ${categoryAPattern[index]}.`);
    }
  });

  Object.entries(totalRules).forEach(([type, expected]) => {
    if (totalCounts[type] !== expected) {
      throw new Error(`El total de ${typeNames[type]} debe ser ${expected}.`);
    }
  });

  Object.entries(tableRules).forEach(([type, brandRules]) => {
    Object.entries(brandRules).forEach(([brandName, categoryRules]) => {
      Object.entries(categoryRules).forEach(([letter, expected]) => {
        if (tableCounts[type][brandName][letter] !== expected) {
          throw new Error(`${brandName} debe tener ${expected} ${typeNames[type]} de categoria ${letter}.`);
        }
      });
    });
  });
}

function renderFeed() {
  const feed = document.querySelector('#feedGrid');
  feed.innerHTML = columns.map(column => `
    <article class="feed-column">
      <header class="column-head">
        <div class="column-title"><span class="legend-dot ${column.color}"></span>${column.name}</div>
        <span class="column-count">${events.filter(event => event.column === column).length.toString().padStart(2, '0')} piezas</span>
      </header>
      ${events.filter(event => event.column === column).map(({ letter, title, type }) => `
        <div class="post">
          <div class="post-top"><span>INSTAGRAM / 2026</span><span>${typeNames[type]}</span></div>
          <span class="post-label">${letter}</span>
          <h4>${title}</h4>
          <div class="post-footer"><span class="post-type">${column.name}</span><span class="post-mark"></span></div>
        </div>`).join('')}
    </article>`).join('');
}

function formatDate(date) {
  return new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(date).replace('.', '');
}

function renderCalendar(filter = 'all') {
  const calendar = document.querySelector('#calendar');
  const dayNames = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
  const firstDay = (startDate.getDay() + 6) % 7;
  const cells = dayNames.map(day => `<div class="weekday">${day}</div>`).join('');
  let days = '';
  for (let empty = 0; empty < firstDay; empty += 1) days += '<div class="day outside"></div>';
  for (let date = new Date(startDate); date <= endDate; date.setDate(date.getDate() + 1)) {
    const dayEvents = events.filter(event => event.date.toDateString() === date.toDateString() && (filter === 'all' || event.type === filter));
    const eventHtml = dayEvents.map(event => `<div class="event ${event.column.slug}-event ${event.type}"><strong>${event.letter} · ${event.title}</strong><small>${event.column.name} / ${typeNames[event.type]}</small></div>`).join('');
    days += `<div class="day"><div class="day-number">${date.getDate()}</div>${eventHtml}</div>`;
  }
  calendar.innerHTML = cells + days;
}

document.querySelectorAll('.filter-button').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.filter-button').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    renderCalendar(button.dataset.filter);
  });
});

document.querySelector('#todayButton').addEventListener('click', () => {
  document.querySelector('#calendarSection').scrollIntoView({ behavior: 'smooth' });
});

validateSchedule();
renderFeed();
renderCalendar();
