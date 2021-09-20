module.exports = {
  siteMetadata: {
    // Site URL for when it goes live
    siteUrl: `https://jeroen.vangoey.be`,
    // Your Name
    name: 'Jeroen Van Goey',
    // Main Site Title
    title: `Jeroen Van Goey | Sr. Software Development Engineer - Machine Learning at Barco`,
    // Description that goes under your name in main bio
    description: `Just Another Genome Hacker`,
    // Optional: Twitter account handle
    author: `@BioGeek`,
    // Optional: Github account URL
    github: `https://github.com/BioGeek`,
    // Optional: LinkedIn account URL
    linkedin: `https://www.linkedin.com/in/jeroenvangoey/`,
    // Content of the About Me section
    about: `Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus perferendis porro cumque ea error ab voluptatem. Temporibus adipisci exercitationem similique itaque quibusdam laudantium, qui molestiae quas, aut amet animi id.`,
    // Optional: List your projects, they must have `name` and `description`. `link` is optional.
    projects: [
      {
        name: 'euler',
        description:
          'My solutions to Project Euler',
        link: 'https://github.com/BioGeek/euler',
      },
      {
        name: 'euler',
        description:
          'My solutions to Advent of Code',
        link: 'https://github.com/BioGeek/adventofcode',
      },
    ],
    // Optional: List your experience, they must have `name` and `description`. `link` is optional.
    experience: [
      {
        name: 'Barco',
        description: 'Sr. Software Development Engineer - Machine Learning, February 2020 - Present',
      },
      {
        name: 'BASF',
        description: 'Bioinformatics Researcher - Manager of the Python and R Platforms, August 2018 - January 2020',
      },
      {
        name: 'Jeroen Van Goey Photography',
        description: 'Freelance Photographer, August 2010 - Present',
        link: 'https://jeroenvangoey.be',
      },
    ],
    // Optional: List your skills, they must have `name` and `description`.
    skills: [
      {
        name: 'Languages & Frameworks',
        description:
          'Python: pandas, NumPy, Tensorflow, BioPython, ...',
      },
      {
        name: 'Bioinformatics',
        description: 'BLAST, ClustalW, Snakemake, BioNumerics,...',
      },
      {
        name: 'Other',
        description:
          'Docker, Amazon Web Services (AWS), CI / CD, ...',
      },
    ],
  },
  plugins: [
    `gatsby-plugin-react-helmet`,
    {
      resolve: `gatsby-source-filesystem`,
      options: {
        name: `images`,
        path: `${__dirname}/src/images`,
      },
    },
    {
      resolve: `gatsby-source-filesystem`,
      options: {
        path: `${__dirname}/content/blog`,
        name: `blog`,
      },
    },
    {
      resolve: `gatsby-transformer-remark`,
      options: {
        plugins: [
          {
            resolve: `gatsby-remark-images`,
            options: {
              maxWidth: 590,
              wrapperStyle: `margin: 0 0 30px;`,
            },
          },
          {
            resolve: `gatsby-remark-responsive-iframe`,
            options: {
              wrapperStyle: `margin-bottom: 1.0725rem`,
            },
          },
          `gatsby-remark-prismjs`,
          `gatsby-remark-copy-linked-files`,
          `gatsby-remark-smartypants`,
        ],
      },
    },
    `gatsby-transformer-sharp`,
    `gatsby-plugin-sharp`,
    `gatsby-plugin-postcss`,
    `gatsby-plugin-feed`,
    {
      resolve: `gatsby-plugin-google-analytics`,
      options: {
        trackingId: `ADD YOUR TRACKING ID HERE`, // Optional Google Analytics
      },
    },
    {
      resolve: `gatsby-plugin-manifest`,
      options: {
        name: `devfolio`,
        short_name: `devfolio`,
        start_url: `/`,
        background_color: `#663399`,
        theme_color: `#663399`, // This color appears on mobile
        display: `minimal-ui`,
        icon: `src/images/icon.png`,
      },
    },
  ],
};
