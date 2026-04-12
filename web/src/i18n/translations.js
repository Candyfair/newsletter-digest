const translations = {
  fr: {
    run:          'Lancer le digest',
    running:      'Pipeline en cours…',
    done:         'Digest prêt',
    error:        'Une erreur est survenue',
    idle:         'Aucun digest généré',
    viewDigest:   'Voir le digest',
    delete:       'Supprimer la sélection',
    cancel:       'Annuler la sélection',   // SummaryList
    cancelPipeline:'Annuler le traitement',  // PipelineControl
    totalEmails:  'newsletters à traiter',
    confirmDelete:'Supprimer les newsletters sélectionnées ?',
    confirmYes:   'Confirmer',
    confirmNo:    'Annuler',
    progress:     'Traitement du message',  // "Traitement du message 2/10"
    theme:        'Thème',
    noDigest:     'Lance le pipeline pour générer un digest.',
  },
  en: {
    run:          'Run digest',
    running:      'Pipeline running…',
    done:         'Digest ready',
    error:        'An error occurred',
    idle:         'No digest generated yet',
    viewDigest:   'View digest',
    delete:       'Delete selection',
    cancel:       'Cancel selection',
    cancelPipeline:'Cancel',
    totalEmails:  'newsletters to process',
    confirmDelete:'Delete selected newsletters?',
    confirmYes:   'Confirm',
    confirmNo:    'Cancel',
    progress:     'Processing message',
    theme:        'Theme',
    noDigest:     'Run the pipeline to generate a digest.',
  },
}

// t('run', 'fr') → 'Lancer le digest'
export function t(key, lang) {
  return translations[lang]?.[key] ?? key
}